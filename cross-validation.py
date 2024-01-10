from unicodedata import name
from models.attention_series import Grade_regressor
import json
import h5py
import ast
import numpy as np
import spectral
from spectral import imshow
from PIL import Image
spectral.settings.envi_support_nonlowercase_params = True
from dataloaders.dataloaders import dataset_iron_balanced_mixed
import torch
from torch.utils.data import DataLoader
from torch.utils.data  import random_split
from trainer import train_regression
from configs.training_cfg import *
import torch
import os

torch.autograd.set_detect_anomaly(True)
pool = torch.nn.AvgPool2d(3,3)
mask_rgb_values = [[255,242,0],[34,177,76],[255,0,88]]
def test_data(list):
    test_data_list = []
    for id in list:
        pixel_list = []
        imgid, sampleid = id.split('_')
        sampleid = ord(sampleid) - 65
        img_data = spectral.envi.open(dataset_path+"/spectral_data/{}-Radiance From Raw Data-Reflectance from Radiance Data and Measured Reference Spectrum.bip.hdr".format(imgid))
        gt = ast.literal_eval(img_data.metadata['gt_TFe'])
        img_data = torch.Tensor(img_data.asarray()/6000)[:,:,:]
        img_data = pool(img_data.permute(2,0,1)).permute(1,2,0)
        mask = np.array(Image.open(dataset_path+"/spectral_data/{}-Radiance From Raw Data-Reflectance from Radiance Data and Measured Reference Spectrum.bip.hdr_mask.png".format(imgid)))
        row, col, _ = img_data.shape
        for r in range(row):
            for c in range(col):
                if mask[r*3+1,c*3+1].tolist() == mask_rgb_values[sampleid]:
                    pixel_list.append(img_data[r,c].unsqueeze(0))

        pixel_list = torch.cat(pixel_list, dim=0)
        test_data_list.append({
            "tensor": pixel_list.to(device),
            "gt": torch.Tensor([gt[sampleid]]).to(device)
        })
    return test_data_list


if __name__ == "__main__":
    # all dataset
    all_samples = ['13_A','11_A','12_A','12_C','25_A','42_B','55_C','15_A',
                '56_B','4_B','42_A','57_A','14_B','36_B','43_C','26_A',
                '9_C','43_A','53_A','3_B','30_C','27_A','22_B','27_C','31_C',
                '53_B','32_A','6_B','52_B','8_B','41_B','31_A','34_A',
                '7_B','53_C','54_C','29_B','16_B','47_A','49_B','10_C',
                '21_C','31_B','50_A','18_A','22_C','52_C','38_A','17_A',
                '59_A','4_A','57_B','33_C','7_A','49_C','58_B','4_C',
                '52_A','17_C','23_A','7_C','46_B','30_B','46_A','18_C',
                '24_A','55_A','40_A','55_B','6_A','59_B','3_C','27_B',
                '18_B','5_A','29_A','25_B','49_A','32_C','45_C','12_B',
                '20_A','9_A','28_C','29_C','5_C','46_C','14_C','19_A',
                '23_B','9_B','40_B','35_C','13_C','50_B','35_B','15_B',
                '44_C','45_A','23_C','1_C','1_B','35_A','32_B','6_C',
                '51_B','28_B','2_B','58_C','38_C','2_A','26_B','2_C',
                '16_C','43_B','24_C','54_B','15_C','42_C','36_A','37_A',
                '41_C','44_B','19_C','51_C','1_A','39_B','28_A','58_A',
                '39_C','30_A','39_A','54_A','61_C','61_A','37_B','48_C',
                '21_A','22_A','48_B','48_A'] + \
                ['14_A',
                '11_C','16_A','13_B','21_B','36_C','31_A','34_B','56_A',
                '47_C','8_A','19_B','3_A','62_A','33_B','10_A','24_B','60_B',
                '11_B','59_C','10_B','60_C','45_B','8_C','41_A','38_B',
                '57_C','50_C','61_B','37_C']

    data = []
    for id in all_samples:
        imgid, sampleid = id.split('_')
        sampleid = ord(sampleid) - 65
        metadata = spectral.envi.open(dataset_path+"/spectral_data/{}-Radiance From Raw Data-Reflectance from Radiance Data and Measured Reference Spectrum.bip.hdr".format(imgid)).metadata
        gt = ast.literal_eval(metadata['gt_TFe'])
        data.append({
            "id": id,
            "gt": torch.Tensor([gt[sampleid]]).to(device)
        })

    # 排序数据集
    data = sorted(data, key=lambda x: x["gt"])
    
    # split data into 5 folds, make each fold has the same distribution
    folds = [[],[],[],[],[]]
    for i in range(len(data)):
        folds[i%5].append(data[i]["id"])

    # training session
    ckpt_path = ckpt_path+"/"+session_tag
    model_name = ""
    if os.path.exists(ckpt_path) and os.path.isdir(ckpt_path):
        # loading training config
        with open(ckpt_path+"/cfg.json", "r") as file:
            cfg_data = json.load(file)
        
                
        # loading ckpt model
        items = os.listdir(ckpt_path)
        fold = 0    # 如果没pt文件，就都是0
        step = 0
        for item in items:
            item_path = os.path.join(ckpt_path, item)
            
            # 检查是否为文件并且以 .pt 为格式
            if os.path.isfile(item_path) and item.endswith(".pt"):
                model_name = item
                # 从model名获得fold与step
                base_name = os.path.splitext(file_name)[0]
                parts = base_name.split("_")
                if int(parts[0][4:]) > fold:
                    fold = int(parts[0][4:])  # 从索引4开始提取 fold 数
                    step = int(parts[1][4:])  # 从索引4开始提取 step 数
        # 开训
        model = Grade_regressor(encoder='TSI').to(device)
        for i in range(fold, 5):
            if i == fold and step != 0:
                model.load_state_dict(torch.load(ckpt_path+"/fold{}_step{}.pt".format(fold, step)))

            training_list = []
            test_list = []
            for j in range(5):
                if j != i:
                    training_list += folds[j]
                else:
                    test_list += folds[j]
            trainset = dataset_iron_balanced_mixed(dataset_path+"/spectral_data_IR_winsize3.csv", 
                                                    dataset_path+"/spectral_data_IR_winsize3.hdf5", 
                                                    cfg_data["step_per_fold"],
                                                    training_list,
                                                    cfg_data["batch_size"],
                                                    balance=True)
            trainloader = DataLoader(trainset, shuffle=True, batch_size=1, num_workers=num_workers, drop_last=True)

            train_regression(trainloader, model, i, 
                            lr=cfg_data["learning_rate"], 
                            tag=cfg_data["session_tag"]+"_fold{}".format(i), 
                            pretrain_step=-1, 
                            lr_decay=cfg_data["lr_decay"], 
                            lr_decay_step=cfg_data["lr_decay_step"], 
                            lr_lower_bound=cfg_data["lr_lower_bound"], 
                            step=step+1, test_data=test_data(test_list), vis=model.visualization)
        
    else:
        # a new training session
        os.mkdir(ckpt_path)
        cfg = {
            "step_per_fold": step_per_fold,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "lr_decay": lr_decay,
            "lr_decay_step": lr_decay_step,
            "lr_lower_bound": lr_lower_bound,
            "session_tag": session_tag
        }

        with open(ckpt_path+"/cfg.json", "w") as file:
            json.dump(cfg, file)    # saving traing config
        # 开训
        model = Grade_regressor(encoder='TSI').to(device)
        for i in range(5):
            training_list = []
            test_list = []
            for j in range(5):
                if j != i:
                    training_list += folds[j]
                else:
                    test_list += folds[j]
            trainset = dataset_iron_balanced_mixed(dataset_path+"/spectral_data_IR_winsize3.csv", 
                                                    dataset_path+"/spectral_data_IR_winsize3.hdf5", 
                                                    step_per_fold,
                                                    training_list,
                                                    batch_size, 
                                                    balance=True)
            trainloader = DataLoader(trainset, shuffle=True, batch_size=1, num_workers=num_workers, drop_last=True)

            train_regression(trainloader, model, i, 
                            lr=learning_rate, 
                            tag=session_tag+"_fold{}".format(i), 
                            pretrain_step=-1, 
                            lr_decay=lr_decay, 
                            lr_decay_step=lr_decay_step, 
                            lr_lower_bound=lr_lower_bound, 
                            step=1, test_data=test_data(test_list), vis=model.visualization)
    


        