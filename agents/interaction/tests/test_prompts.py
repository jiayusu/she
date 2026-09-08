"""FR-E01 · 人格提示词系统（版本化冻结/盲测区分）+ FR-E10 · DLC 三件套注册。"""

import os

import pytest

from she_engine.prompts import MinisterRegistry

ASSETS = "assets"
MINISTERS = ["xiaop", "laonie", "xingxing", "ahai", "wangguan"]


@pytest.fixture(scope="module")
def registry() -> MinisterRegistry:
    r = MinisterRegistry(ASSETS + "/ministers")
    assert not r.load_errors, f"bad prompt files: {r.load_errors}"
    return r


def test_all_five_ministers_registered(registry):
    assert sorted(registry.ids()) == sorted(MINISTERS)


def test_dlc_three_piece_complete(registry):
    """FR-E10 三件套：提示词文件 + 音色 ID + 灯色。"""
    for mid in MINISTERS:
        spec = registry.get(mid)
        assert spec.voice_id and spec.light_color.startswith("#")
        assert spec.system_prompt.strip()
        assert spec.personality.strip() and spec.catchphrases and spec.prohibitions


def test_render_fills_all_placeholders(registry):
    for mid in MINISTERS:
        spec = registry.get(mid)
        text = spec.render_system("LEVEL RULES", "SCENE", "RECAST", "CTX", "OUTPUT")
        for piece in ("LEVEL RULES", "SCENE", "CTX", "OUTPUT"):
            assert piece in text
        assert "{" not in text  # 所有占位符都已填充（冻结校验）


def test_render_rejects_bad_prompt(tmp_path):
    """占位符写错的提示词文件在渲染时立刻暴露（冻结校验）。"""
    d = tmp_path / "bad" / "v1.yaml"
    d.parent.mkdir(parents=True)
    d.write_text(
        "id: bad\nname: Bad\nversion: 1\nvoice_id: v\nlight_color: '#fff'\n"
        "system_prompt: |-\n  hello {typo_placeholder}\n",
        encoding="utf-8",
    )
    r = MinisterRegistry(str(tmp_path))
    spec_obj = r.get("bad")
    with pytest.raises(ValueError):
        spec_obj.render_system("L", "S")


def test_version_rollback(registry):
    """提示词全部进版本库：可回滚到任意历史版本。"""
    v1 = registry.get("xiaop", version=1)
    assert v1.version == 1
    assert registry.pinned_version("xiaop") >= 1
    registry.rollback("xiaop", 1)
    assert registry.pinned_version("xiaop") == 1


def test_dlc_registration_without_code_change(tmp_path):
    """FR-E10：新增人格 = 丢一个 YAML 文件，不改任何代码。"""
    dlc = tmp_path / "mengmeng" / "v1.yaml"
    dlc.parent.mkdir(parents=True)
    dlc.write_text(
        "id: mengmeng\nname: 萌萌\nversion: 1\nvoice_id: cat_mengmeng_v1\n"
        "light_color: '#00FFAA'\npersonality: 好奇的小猫\ntone: 软软的\n"
        "catchphrases: [喵呜~]\nprohibitions: [不吓人]\nstyle_rules: [短句]\n"
        "system_prompt: |-\n  You are 萌萌. {personality} {level_rules} {scene_directive}"
        " {recast_directive} {ctx_block} {output_format}\n"
        "blind_markers: [喵]\n",
        encoding="utf-8",
    )
    r = MinisterRegistry(ASSETS + "/ministers")
    spec = r.register_file(str(dlc))
    assert spec.id == "mengmeng" and spec.voice_id == "cat_mengmeng_v1"
    assert "mengmeng" in r.ids()
    # 渲染即可用
    text = spec.render_system("L", "S", "R", "C", "O")
    assert "萌萌" in text


def test_wrong_dir_name_rejected(tmp_path):
    d = tmp_path / "notmatching" / "v1.yaml"
    d.parent.mkdir(parents=True)
    d.write_text(
        "id: other\nname: O\nversion: 1\nvoice_id: v\nlight_color: '#fff'\n"
        "system_prompt: x {level_rules} {scene_directive} {recast_directive} {ctx_block} {output_format}\n",
        encoding="utf-8",
    )
    r = MinisterRegistry(str(tmp_path))
    assert "other" not in r.ids()
    assert r.load_errors  # 目录名与 id 不一致 → 明确报错


def test_missing_required_field_reported(tmp_path):
    d = tmp_path / "nop" / "v1.yaml"
    d.parent.mkdir(parents=True)
    d.write_text("id: nop\nname: N\nversion: 1\n", encoding="utf-8")
    r = MinisterRegistry(str(tmp_path))
    assert "nop" not in r.ids()
    assert r.load_errors  # 缺字段被记录，不静默