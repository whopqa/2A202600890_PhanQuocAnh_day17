from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.dataset import decontaminate, decontaminate_vn_support_pairs


def main() -> None:
    eval_set = [
        {"trace_id": "t_eval", "input": "Đơn hàng #123 của tôi đang ở đâu?", "reference": "Đang giao"}
    ]
    pairs = [
        {"prompt": "Don hang 123 cua toi dang o dau", "chosen": "Đơn đang giao", "rejected": "Không rõ"},
        {"prompt": "Chính sách đổi trả cho widget là gì?", "chosen": "Đổi trả 30 ngày", "rejected": "Không hỗ trợ"},
    ]

    exact_clean = decontaminate(pairs, eval_set)
    vn_clean = decontaminate_vn_support_pairs(pairs, eval_set)

    print("=== Bonus prototype: VN decontamination ===")
    print(f"exact-match keeps  : {len(exact_clean)} pairs")
    print(f"vn-normalized keeps: {len(vn_clean)} pairs")


if __name__ == "__main__":
    main()
