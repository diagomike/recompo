"""Face boxes over a time range of a video, with YuNet (ONNX) under onnxruntime, for face-centred vertical crops.

    python faces.py --model yunet.onnx --input movie.mkv --start 389.4 --dur 15.6 --fps 4 --ffmpeg ffmpeg --out faces.json
Writes {"width", "height", "fps", "samples": [{"t": seconds from start, "faces": [[x, y, w, h, score], …]}]}
with boxes in the source's pixels. Frames come from ffmpeg (no OpenCV needed).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import numpy as np

SIZE = 640                 # the model's fixed input
STRIDES = (8, 16, 32)


def decode(outs: dict, scale: float, thresh: float = 0.6, iou: float = 0.3) -> list[list[float]]:
    """YuNet's anchor-free outputs → boxes [x, y, w, h, score] in the frame's pixels (as OpenCV's FaceDetectorYN)."""
    boxes, scores = [], []
    for s in STRIDES:
        cols = SIZE // s
        cls = np.clip(outs[f"cls_{s}"][0, :, 0], 0, 1)
        obj = np.clip(outs[f"obj_{s}"][0, :, 0], 0, 1)
        score = np.sqrt(cls * obj)
        keep = np.where(score >= thresh)[0]
        if not len(keep):
            continue
        bb = outs[f"bbox_{s}"][0, keep]
        r, c = keep // cols, keep % cols
        cx, cy = (c + bb[:, 0]) * s, (r + bb[:, 1]) * s
        w, h = np.exp(bb[:, 2]) * s, np.exp(bb[:, 3]) * s
        boxes.append(np.stack([cx - w / 2, cy - h / 2, w, h], axis=1))
        scores.append(score[keep])
    if not boxes:
        return []
    b, sc = np.concatenate(boxes), np.concatenate(scores)
    order, out = np.argsort(-sc), []
    while len(order):
        i = order[0]
        out.append(i)
        x1 = np.maximum(b[i, 0], b[order[1:], 0]); y1 = np.maximum(b[i, 1], b[order[1:], 1])
        x2 = np.minimum(b[i, 0] + b[i, 2], b[order[1:], 0] + b[order[1:], 2])
        y2 = np.minimum(b[i, 1] + b[i, 3], b[order[1:], 1] + b[order[1:], 3])
        inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        union = b[i, 2] * b[i, 3] + b[order[1:], 2] * b[order[1:], 3] - inter
        order = order[1:][inter / np.maximum(union, 1e-6) < iou]
    return [[round(float(v) / scale, 1) for v in b[i]] + [round(float(sc[i]), 3)] for i in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--width", type=int, required=True, help="the source's display width")
    ap.add_argument("--height", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import onnxruntime as ort

    sess = ort.InferenceSession(a.model, providers=["CPUExecutionProvider"])
    names = [o.name for o in sess.get_outputs()]
    scale = SIZE / max(a.width, a.height)          # long side → 640, the rest padded
    fw, fh = int(round(a.width * scale)) // 2 * 2, int(round(a.height * scale)) // 2 * 2
    cmd = [a.ffmpeg, "-v", "error", "-ss", f"{a.start:.3f}", "-t", f"{a.dur:.3f}", "-i", a.input, "-an", "-sn",
           "-vf", f"fps={a.fps},scale={fw}:{fh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            creationflags=0x08000000 if sys.platform == "win32" else 0)
    frame_bytes = fw * fh * 3
    canvas = np.zeros((SIZE, SIZE, 3), np.float32)
    samples, k = [], 0
    total = max(1, int(a.dur * a.fps))
    while True:
        raw = proc.stdout.read(frame_bytes)
        if len(raw) < frame_bytes:
            break
        canvas[:] = 0
        canvas[:fh, :fw] = np.frombuffer(raw, np.uint8).reshape(fh, fw, 3)
        blob = canvas.transpose(2, 0, 1)[None]
        outs = dict(zip(names, sess.run(None, {"input": blob})))
        samples.append({"t": round(k / a.fps, 3), "faces": decode(outs, scale)})
        k += 1
        if k % 20 == 0:
            sys.stdout.write(json.dumps({"progress": min(0.99, k / total), "message": f"{k} frames"}) + "\n")
            sys.stdout.flush()
    proc.wait()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"width": a.width, "height": a.height, "fps": a.fps, "samples": samples}, f)
    sys.stdout.write(json.dumps({"progress": 1.0, "message": f"{k} frames", "frames": k}) + "\n")


if __name__ == "__main__":
    main()
