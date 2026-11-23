"""Tiến trình riêng chạy PyTorch.

Trên macOS + Anaconda, PyTorch và XGBoost/scikit-learn nạp hai bản OpenMP khác nhau
trong cùng một tiến trình -> segfault/treo. Vì vậy mạng LSTM được huấn luyện trong
một tiến trình con độc lập (chỉ nạp numpy + torch), giao tiếp bằng pickle qua stdin/stdout.
"""
from __future__ import annotations

import pickle
import subprocess
import sys


class _Conn:
    def __init__(self, rf, wf):
        self.rf, self.wf = rf, wf

    def recv(self):
        return pickle.load(self.rf)

    def send(self, obj):
        pickle.dump(obj, self.wf, protocol=pickle.HIGHEST_PROTOCOL)
        self.wf.flush()


def _serve(conn: _Conn, seed: int):
    import torch
    from torch import nn

    torch.manual_seed(seed)
    torch.set_num_threads(2)

    class Net(nn.Module):
        def __init__(self, n_in, hidden):
            super().__init__()
            self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
            self.drop = nn.Dropout(0.2)
            self.head = nn.Linear(hidden, 1)

        def forward(self, x):
            o, _ = self.lstm(x)
            return self.head(self.drop(o[:, -1])).squeeze(-1)

    nets: dict = {}
    while True:
        try:
            msg = conn.recv()
        except EOFError:
            break
        cmd = msg[0]
        if cmd == "stop":
            break
        if cmd == "fit":
            _, key, S, Y, W, epochs, hidden, lr = msg
            if key not in nets:
                net = Net(S.shape[2], hidden)
                opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
                nets[key] = (net, opt)
            net, opt = nets[key]
            S, Y, W = map(torch.from_numpy, (S, Y, W))
            loss_fn = nn.HuberLoss(reduction="none", delta=1.0)
            n = len(Y)
            net.train()
            for _ in range(epochs):
                perm = torch.randperm(n)
                for b in range(0, n, 64):
                    j = perm[b:b + 64]
                    opt.zero_grad()
                    loss = (loss_fn(net(S[j]), Y[j]) * W[j]).sum() / W[j].sum()
                    loss.backward()
                    nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                    opt.step()
            conn.send("ok")
        elif cmd == "predict":
            _, key, S = msg
            net, _ = nets[key]
            net.eval()
            with torch.no_grad():
                conn.send(net(torch.from_numpy(S)).numpy())


class TorchWorker:
    _inst = None

    @classmethod
    def get(cls, seed: int = 42) -> "TorchWorker":
        if cls._inst is None or cls._inst.proc.poll() is not None:
            cls._inst = cls(seed)
        return cls._inst

    def __init__(self, seed: int):
        self.proc = subprocess.Popen([sys.executable, "-u", __file__, str(seed)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.conn = _Conn(self.proc.stdout, self.proc.stdin)

    def call(self, *msg):
        self.conn.send(msg)
        return self.conn.recv()


if __name__ == "__main__":
    import torch  # noqa: F401  (nạp torch đầu tiên trong tiến trình con)
    out = sys.stdout.buffer
    sys.stdout = sys.stderr  # mọi print khác đi ra stderr để không làm hỏng giao thức
    _serve(_Conn(sys.stdin.buffer, out), int(sys.argv[1]) if len(sys.argv) > 1 else 42)
