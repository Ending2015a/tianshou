import warnings
from typing import Any, Tuple, Callable, Optional

from torch.utils.tensorboard import SummaryWriter
from tensorboard.backend.event_processing import event_accumulator

from tianshou.utils.logger.base import BaseLogger, LOG_DATA_TYPE


class TensorboardLogger(BaseLogger):
    """A logger that relies on tensorboard SummaryWriter by default to visualize \
    and log statistics.

    :param SummaryWriter writer: the writer to log data.
    :param int train_interval: the log interval in log_train_data(). Default to 1000.
    :param int test_interval: the log interval in log_test_data(). Default to 1.
    :param int update_interval: the log interval in log_update_data(). Default to 1000.
    :param int save_interval: the save interval in save_data(). Default to 1 (save at
        the end of each epoch).
    """

    def __init__(
        self,
        writer: SummaryWriter,
        train_interval: int = 1000,
        test_interval: int = 1,
        update_interval: int = 1000,
        save_interval: int = 1,
    ) -> None:
        super().__init__(train_interval, test_interval, update_interval)
        self.save_interval = save_interval
        self.last_save_step = -1
        self.writer = writer

    def write(self, step_type: str, step: int, data: LOG_DATA_TYPE) -> None:
        for k, v in data.items():
            self.writer.add_scalar(k, v, global_step=step)

    def save_data(
        self,
        epoch: int,
        env_step: int,
        gradient_step: int,
        save_checkpoint_fn: Optional[Callable[[int, int, int], None]] = None,
    ) -> None:
        if save_checkpoint_fn and epoch - self.last_save_step >= self.save_interval:
            self.last_save_step = epoch
            save_checkpoint_fn(epoch, env_step, gradient_step)
            self.write("save/epoch", epoch, {"save/epoch": epoch})
            self.write("save/env_step", env_step, {"save/env_step": env_step})
            self.write("save/gradient_step", gradient_step,
                       {"save/gradient_step": gradient_step})

    def restore_data(self) -> Tuple[int, int, int]:
        ea = event_accumulator.EventAccumulator(self.writer.log_dir)
        ea.Reload()

        try:  # epoch / gradient_step
            epoch = ea.scalars.Items("save/epoch")[-1].step
            self.last_save_step = self.last_log_test_step = epoch
            gradient_step = ea.scalars.Items("save/gradient_step")[-1].step
            self.last_log_update_step = gradient_step
        except KeyError:
            epoch, gradient_step = 0, 0
        try:  # offline trainer doesn't have env_step
            env_step = ea.scalars.Items("save/env_step")[-1].step
            self.last_log_train_step = env_step
        except KeyError:
            env_step = 0

        return epoch, env_step, gradient_step


class BasicLogger(TensorboardLogger):
    """BasicLogger has changed its name to TensorboardLogger in #427.

    This class is for compatibility.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        warnings.warn(
            "Deprecated soon: BasicLogger has renamed to TensorboardLogger in #427.")
        super().__init__(*args, **kwargs)
