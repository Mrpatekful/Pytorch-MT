import numpy
import torch

from utils.config import Config

numpy.random.seed(2)
torch.manual_seed(2)

TASK_CONFIG = 'configs/tasks/nmt.json'


def main():
    task = Config(TASK_CONFIG).assemble()
    task.fit_model(epochs=10)


if __name__ == '__main__':
    main()
