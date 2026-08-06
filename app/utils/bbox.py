VALID_FORMATS = {"xyxy", "xywh", "points", "xy"}


def convert_bbox(quad: dict, fmt: str):
    if not quad:
        return None

    xs = [quad["x1"], quad["x2"], quad["x3"], quad["x4"]]
    ys = [quad["y1"], quad["y2"], quad["y3"], quad["y4"]]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    if fmt == "xyxy":
        return [round(x_min), round(y_min), round(x_max), round(y_max)]
    if fmt == "xywh":
        return [round(x_min), round(y_min), round(x_max - x_min), round(y_max - y_min)]
    if fmt == "points":
        return [
            [round(quad["x1"]), round(quad["y1"])],
            [round(quad["x2"]), round(quad["y2"])],
            [round(quad["x3"]), round(quad["y3"])],
            [round(quad["x4"]), round(quad["y4"])],
        ]
    if fmt == "xy":
        return [
            round(quad["x1"]), round(quad["y1"]),
            round(quad["x2"]), round(quad["y2"]),
            round(quad["x3"]), round(quad["y3"]),
            round(quad["x4"]), round(quad["y4"]),
        ]
    raise ValueError(f"bbox_format khong hop le: {fmt}")