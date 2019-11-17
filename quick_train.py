"""
quick train
"""
import torch
import numpy as np
import torchvision.models as torch_models
import torchvision.transforms as transforms

from tqdm import tqdm
from torch import nn
from torchsummary import summary

# private libs
from data.loader import ProbaVLoader
from models.simple_autoencoder import autoencoder
from models.resnet import resnet18_AE, resnet50_AE
from losses import ProbaVLoss


# hyperparameters
BATCH_SIZE = 2
WORKERS = 8
LEARNING_RATE = 0.0001
NUM_EPOCHS = 2000  # since each data point has at least 19 input samples
SUMMARY = False
PRETRAINED = False
CHECKPOINT_PATH = "./checkpoints/checkpoint.ckpt"
USE_MASK = True


train_dataloader = ProbaVLoader("./data/train", to_tensor=True)
train_data = torch.utils.data.DataLoader(
    train_dataloader,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=WORKERS,
    pin_memory=True,
)


# model = autoencoder().cuda()
model = resnet50_AE(pretrained=PRETRAINED).cuda()
if SUMMARY:
    summary(model, (3, 128, 128))
# exit(0)

# criterion = nn.MSELoss()
criterion = ProbaVLoss(mask_flag=USE_MASK)
optimizer = torch.optim.Adam(
    model.parameters(), lr=LEARNING_RATE
)  # , weight_decay=1e-5
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode="min", factor=0.8, patience=3, verbose=True, min_lr=1e-8
)

# load existing model
try:
    # check if checkpoints file of weights file
    checkpoint = torch.load(CHECKPOINT_PATH)
    # pretrained_dict = checkpoint["model_state_dict"]
    # model_dict = model.state_dict()
    # pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict}
    # model.load_state_dict(pretrained_dict, strict=False)

    model.load_state_dict(checkpoint["model_state_dict"], strict=False)
    # optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    epoch_chk = checkpoint["epoch"]
    loss = checkpoint["loss"]
    print("\n\nModel Loaded; ", CHECKPOINT_PATH)
except Exception as e:
    print("\n\nModel not loaded; ", CHECKPOINT_PATH)
    print("Exception: ", e)
    epoch_chk = 0

model.train()
for epoch in range(NUM_EPOCHS):
    if epoch < epoch_chk:
        continue
    losses = []
    # pbar = tqdm(range(len(train_data)))
    for data in train_data:
        img = data["input_image"].cuda()
        target = data["target_image"].cuda()
        img_mask = data["input_mask"].cuda()
        target_mask = data["target_mask"].cuda()

        # print(img.shape)
        # exit(0)
        # ===================forward=====================
        output_lo, output = model(img)
        loss = criterion(
            output_lo.mul(255.0),
            output.mul(255.0),
            target.mul(255.0),
            img_mask,
            target_mask,
        )
        losses.append(loss.item())
        # ===================backward====================
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        # pbar.set_description(
        #     "Epoch: {:5d}; Loss: {:8.5f}".format(epoch, np.mean(losses))
        # )
        # pbar.update()
    scheduler.step(np.mean(losses))
    # ===================log========================
    print("epoch [{}/{}], loss:{:.4f}".format(epoch + 1, NUM_EPOCHS, np.mean(losses)))
    # save checkpoint
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "loss": np.mean(losses),
        },
        CHECKPOINT_PATH,
    )

torch.save(model.state_dict(), "./proba_v.weights")

