import pytest


class FakeLandmark:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


def make_landmarks(nose_z=0.0, l_sh_z=0.0, r_sh_z=0.0, l_sh_y=0.5, r_sh_y=0.5):
    """Return a 33-element landmark list with the indices pose.py reads.

    Index 0 = nose, 11 = left shoulder, 12 = right shoulder.
    """
    lms = [FakeLandmark() for _ in range(33)]
    lms[0] = FakeLandmark(z=nose_z)
    lms[11] = FakeLandmark(y=l_sh_y, z=l_sh_z)
    lms[12] = FakeLandmark(y=r_sh_y, z=r_sh_z)
    return lms


@pytest.fixture
def landmarks_factory():
    return make_landmarks
