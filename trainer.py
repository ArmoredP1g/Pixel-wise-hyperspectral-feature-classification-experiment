from torch.optim import Adam
import torch
from torch.nn import CrossEntropyLoss
from torch.utils.tensorboard import SummaryWriter
from configs.training_cfg import device

def train_classifier(train_loader, test_loader, model, epoch, lr=0.001, tag="unamed", vis=None):
    sum_writer = SummaryWriter("./runs/{}".format(tag))
    
    optimizer = Adam(model.parameters(),
                    lr=lr,
                    betas=(0.9, 0.999),
                    eps=1e-08,
                    weight_decay=0.00001,
                    amsgrad=False)
    loss_fn = CrossEntropyLoss()
    
    total_step = 0
    loss_sum = 0
    for epoch in range(epoch):
        for _, (data, label) in enumerate(train_loader, 0):
            total_step += 1
            label = torch.Tensor(label).to(device)
            output = model(data.to(device))
            optimizer.zero_grad()
            loss = loss_fn(output, label-1) #0是无效的
            loss.backward()
            optimizer.step()

            loss_sum += loss
            if total_step%50 == 0:
                print("loss: {}".format(loss))

            if total_step%200 == 0:
                sum_writer.add_scalar(tag='loss',
                                        scalar_value=loss_sum / 200,
                                        global_step=total_step
                                    )
                loss_sum = 0

            # 可视化内容
            if total_step%10000 == 0:
                if vis != None:
                    vis(sum_writer, total_step)

            if total_step % 20000 == 0:
                # 测试集测试准确率
                correct = 0
                for  _, (data, label) in enumerate(test_loader, 0):
                    label = torch.Tensor(label).to(device)
                    output = model(data.to(device))
                    prediction = torch.argmax(output, dim=1)
                    correct += (prediction == label-1).sum().item()

                acc = correct/(test_loader.__len__()*8) * 100
                sum_writer.add_scalar(tag='acc',
                                scalar_value=acc,
                                global_step=total_step
                            )
                torch.save(model.state_dict(), "./ckpt/{}_{}.pt".format(tag, total_step))


    torch.save(model.state_dict(), "./ckpt/{}_{}.pt".format(tag, total_step))
                               

def train_regression(train_loader, test_loader, model, epoch, lr=0.001, tag="unamed", vis=None):
    sum_writer = SummaryWriter("./runs/{}".format(tag))
    optimizer = Adam(model.parameters(),
                    lr=lr,
                    betas=(0.9, 0.999),
                    eps=1e-08,
                    weight_decay=0.00001,
                    amsgrad=False)
    
    total_step = 0
    loss_sum = 0
    for epoch in range(epoch):
        for _, (data, gt) in enumerate(train_loader, 0):
            total_step += 1
            label = torch.Tensor(gt['gt_TFe']).to(device)
            output = model(data.to(device).squeeze(0))
            optimizer.zero_grad()
            loss = (output.mean()-label).pow(2)
            loss.backward()
            optimizer.step()

            loss_sum += loss
            if total_step%50 == 0:
                print("loss: {}".format(loss.item()))

            if total_step%200 == 0:
                sum_writer.add_scalar(tag='loss',
                                        scalar_value=loss_sum / 200,
                                        global_step=total_step
                                    )
                loss_sum = 0

            # 可视化内容
            if total_step%10000 == 0:
                if vis != None:
                    vis(sum_writer, total_step)

            if total_step % 2000 == 0:
                # 测试集测试均方误差
                total_mse = 0
                for  _, (data, label) in enumerate(test_loader, 0):
                    label = torch.Tensor(label).to(device)
                    output = model(data.to(device))
                    total_mse += (output.mean()-label).pow(2)

                avg_mse = total_mse/(test_loader.__len__()*8)
                sum_writer.add_scalar(tag='平均MSE',
                                scalar_value=avg_mse,
                                global_step=total_step
                            )
                torch.save(model.state_dict(), "./ckpt/{}_{}.pt".format(tag, total_step))


    torch.save(model.state_dict(), "./ckpt/{}_{}.pt".format(tag, total_step))