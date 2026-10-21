"""Face-centred crops (render/faces.py): which face leads, steady per shot, jumps at cuts, pans when it moves."""

from recomp.render import faces

W, H = 1920, 1080          # source
OW, OH = 1080, 1920        # vertical frame: the picture is scaled to 3413 px wide, a 1080 px window is kept


def samples(fn, dur=8.0, fps=4):
    return [{"t": k / fps, "faces": fn(k / fps)} for k in range(int(dur * fps))]


def x_of(cx):  # crop x for a face centred at cx (source px)
    s = OH / H
    return round(min(max(cx * s - OW / 2, 0), W * s - OW), 1)


def test_one_steady_face_gives_one_crop():
    keys = faces.keyframes(samples(lambda t: [[1400, 300, 200, 260, 0.9]]), [], 8.0, W, H, OW, OH)
    assert keys == [(0.0, x_of(1500))]


def test_main_face_is_the_big_central_one_and_stays_put_in_a_two_shot():
    # a big face left of centre and a small one at the right edge; then the small one gets slightly bigger
    def two(t):
        return [[700, 300, 220, 280, 0.9], [1650, 350, 120, 150, 0.9 if t < 4 else 0.95]]
    keys = faces.keyframes(samples(two), [], 8.0, W, H, OW, OH)
    assert keys == [(0.0, x_of(810))]


def test_a_cut_jumps_to_the_next_shots_face():
    def shot(t):
        return [[300, 300, 200, 260, 0.9]] if t < 4 else [[1500, 300, 200, 260, 0.9]]
    keys = faces.keyframes(samples(shot), [4.0], 8.0, W, H, OW, OH)
    assert keys == [(0.0, x_of(400)), (3.999, x_of(400)), (4.0, x_of(1600))]
    expr = faces.crop_expr(keys)
    assert expr.startswith("if(lt(t,3.999)") and str(x_of(1600)) in expr


def test_a_shot_without_a_face_keeps_its_neighbours_crop_and_no_face_at_all_falls_back():
    def shot(t):
        return [] if t < 4 else [[1500, 300, 200, 260, 0.9]]
    keys = faces.keyframes(samples(shot), [4.0], 8.0, W, H, OW, OH)
    assert keys[0] == (0.0, x_of(1600)) and keys[-1] == (4.0, x_of(1600))
    assert faces.keyframes(samples(lambda t: []), [], 8.0, W, H, OW, OH) is None


def test_a_walking_person_is_followed_with_pans():
    keys = faces.keyframes(samples(lambda t: [[200 + 180 * t, 300, 200, 260, 0.9]]), [], 8.0, W, H, OW, OH)
    xs = [x for _, x in keys]
    assert len(keys) >= 3 and xs == sorted(xs) and xs[-1] > xs[0]


def test_a_picture_no_wider_than_the_frame_is_not_cropped():
    assert faces.keyframes(samples(lambda t: [[100, 100, 50, 50, 0.9]]), [], 8.0, 1080, 1920, OW, OH) is None
