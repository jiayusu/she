"""FR-E07 · 兜底模板库：每大臣 ≥50 条，万物/朝会/安抚场景覆盖，拔网线 100% 回应。"""

import pytest

from she_engine.templates import REQUIRED_SCENES, SCENES, TemplateLibrary

MINISTERS = ["xiaop", "laonie", "xingxing", "ahai", "wangguan"]
ASSETS = "assets"


@pytest.fixture(scope="module")
def library() -> TemplateLibrary:
    lib = TemplateLibrary()
    n = lib.load_dir(ASSETS + "/templates")
    assert n > 0
    return lib


def test_every_minister_has_50_plus(library):
    for m in MINISTERS:
        assert library.count(m) >= 50, f"{m} has only {library.count(m)}"


def test_required_scenes_covered(library):
    """FR-E07 点名：万物/朝会/安抚三类场景。"""
    for m in MINISTERS:
        for scene in REQUIRED_SCENES:
            assert library.scene_count(m, scene) > 0, f"{m}/{scene} empty"


def test_pick_returns_scene_match(library):
    t = library.pick("xiaop", "court")
    assert t is not None and t.scene == "court" and t.minister == "xiaop"


def test_pick_avoids_immediate_repeat(library):
    ids = {library.pick("ahai", "comfort").id for _ in range(4)}
    assert len(ids) >= 3  # 轮转生效，不会一直同一条


def test_unknown_minister_returns_none(library):
    assert library.pick("nobody", "court") is None


def test_render_slots_and_scaffold(library):
    t = next(t for t in library.all_templates("xiaop") if t.slots == ("task",))
    out = t.render(task="a fruit")
    assert "a fruit" in out and "|" in out
    # 未提供的 slot → 开发期可见标记，不抛异常
    out2 = t.render()
    assert "?task" in out2


def test_all_templates_render_with_slot_vars(library):
    """全量模板在合法 slot 值下都能渲染（模板抽查 100% 达标的自动化版）。"""
    for t in library.all_templates():
        vars = {s: "apple" for s in t.slots}
        out = t.render(**vars)
        assert out and "?{" not in out
        if t.slots:
            assert "?apple" not in out


def test_stats_shape(library):
    stats = library.stats()
    for m in MINISTERS:
        assert set(stats[m]) == set(SCENES)
