import torch.nn as nn
import torch
from torch.nn.functional import pad
from torch.nn.functional import leaky_relu
import numpy as np
from models.ProbSparse_Self_Attention import ProbSparse_Self_Attention_Block, Self_Attention_Decoder
from models.PositionEmbedding import positionalencoding1d
from configs.training_cfg import device
import seaborn as sns
import matplotlib.pyplot as plt
plt.rcParams['font.size'] = 9 
# plt.rcParams['figure.figsize'] = 20,3

class Spec_Encoder_Linear(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.up_sampling_0 = nn.Conv2d(64,128,1,1,bias=True)
        self.up_sampling_1 = nn.Conv2d(128,256,1,1,bias=True)
        self.up_sampling_2 = nn.Conv2d(256,512,1,1,bias=True)

        self.soft = nn.Softmax(dim=2)
        self.weight_mask = nn.Parameter(torch.ones(16,1,42,42,1)/1e6)   # multiplied with: head(8), batch, row, col, dim

    def forward(self, x):
        x_norm=((x-x.min(dim=1)[0].unsqueeze(1))/(x.max(dim=1)[0]-x.min(dim=1)[0]+1e-5).unsqueeze(1))    # [batch, 168]

        DI = x.unsqueeze(1)-x.unsqueeze(2)  # [batch, 168, 168]
        NDI = (x.unsqueeze(1)-x.unsqueeze(2))/(x.unsqueeze(1)+x.unsqueeze(2)+1e-5)
        DI_NORM = x_norm.unsqueeze(1)-x_norm.unsqueeze(2)  # [batch, 168, 168]
        NDI_NORM = (x_norm.unsqueeze(1)-x_norm.unsqueeze(2))/(x_norm.unsqueeze(1)+x_norm.unsqueeze(2)+1e-5)

        x = torch.cat([DI.unsqueeze(3), NDI.unsqueeze(3), DI_NORM.unsqueeze(3), NDI_NORM.unsqueeze(3)], dim=3)   # [batch, 168, 168, 4]
        del DI, NDI, DI_NORM, NDI_NORM
        b,r,c,d = x.shape

        # tensor split
        new_tensor = []
        for row in range(4):
            for col in range(4):
                new_tensor.append(x[:,row*42:(row+1)*42,col*42:(col+1)*42,:])

        x = torch.cat(new_tensor, dim=3) # [batch, 42, 42, 64]

        x = torch.relu(self.up_sampling_0(x.permute(0,3,1,2)))
        x = torch.relu(self.up_sampling_1(x))
        x = torch.relu(self.up_sampling_2(x))
        x = x.permute(0,2,3,1)  # [b, 42, 42, 512]


        x = torch.cat(list(x.unsqueeze(0).split(32,4)), dim=0)     # [16, b, 42, 42, 32]
        x = x*self.soft(self.weight_mask.reshape(16,1,42*42,1)).reshape(16,1,42,42,1)  # [16, b, 21, 21, 32]
        x = x.sum(dim=(2,3))   # [16,b,32]
        x = x.transpose(0,1).reshape(b,512) # [batch, 512]
        return torch.relu(x)


class Spec_Decoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.dropout = nn.Dropout(p=0.2)
        self.ln1 = nn.LayerNorm(256)
        self.ln2 = nn.LayerNorm(128)
        self.ln3 = nn.LayerNorm(64)
        self.fc0 = nn.Linear(512,256)
        self.fc1 = nn.Linear(256,128)
        self.fc2 = nn.Linear(128,64)
        self.fc_out = nn.Linear(64,1)

    def forward(self, x):
        x = self.ln1(self.fc0(x))
        x = torch.tanh(x)
        x = self.ln2(self.fc1(x))
        x = torch.tanh(x)
        x = self.ln3(self.fc2(x))
        x = torch.tanh(x)
        x = (torch.tanh(self.fc_out(x)) + 1)*0.5
        # x = self.fc_out(x)
        # x = torch.clamp(x, min=0, max=1)
        return x


class Grade_regressor(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = Spec_Encoder_Linear()
        self.decoder1 = Spec_Decoder()
        # self.decoder2 = Spec_Decoder()
        # self.decoder3 = Spec_Decoder()
        # self.decoder4 = Spec_Decoder()
        # self.decoder5 = Spec_Decoder()

    def forward(self, x):
        x = self.encoder(x)
        x = torch.cat([
            self.decoder1(x)
            # self.decoder2(x),
            # self.decoder3(x),
            # self.decoder4(x),
            # self.decoder5(x),
        ], dim=1)

        return x
    
    def visualization(self, sum_writer, scale):
        '''
        朝tensorboard输出可视化内容
        '''
        for i in range(16):
            axexSub_attn = sns.heatmap(torch.abs(self.encoder.weight_mask.squeeze(4).squeeze(1)).cpu().detach().numpy()[i], cmap="viridis", xticklabels=False, yticklabels=False)
            # axexSub_attn = sns.heatmap(torch.abs(self.encoder.weight_mask.squeeze(1).squeeze(1)).cpu().detach().numpy()[i], cmap="viridis", xticklabels=False, yticklabels=False)
            sum_writer.add_figure('heatmap_attn/head{}'.format(i), axexSub_attn.figure, scale)# 得.figure转一下