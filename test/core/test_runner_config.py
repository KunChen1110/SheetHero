from importlib.util import module_from_spec, spec_from_file_location
import importlib
import io
from pathlib import Path
from contextlib import redirect_stdout

from src.backend.config.settings import Config


def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[2] / relative_path
    spec = spec_from_file_location(name, module_path)
    module = module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


run_test = _load_module("run_test_module", "test/core/run_test.py")
test_user_case = _load_module("test_user_case_module", "test/core/test_user_case.py")


def test_config_honors_environment_overrides(monkeypatch):
    monkeypatch.setenv("SHEETHERO_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("SHEETHERO_DEPLOYMENT", "qwen3:8b")
    monkeypatch.setenv("SHEETHERO_API_KEY", "")

    config = Config()

    assert config.base_url == "http://localhost:11434/v1"
    assert config.deployment == "qwen3:8b"
    assert config.api_key == ""


def test_apply_runtime_config_overrides_sets_offline_model():
    config = Config()
    args = type(
        "Args",
        (),
        {
            "base_url": None,
            "deployment": None,
            "api_key": None,
            "offline_model": "qwen3:8b",
        },
    )()

    run_test.apply_runtime_config_overrides(config, args)

    assert config.base_url == "http://localhost:11434/v1"
    assert config.deployment == "qwen3:8b"
    assert config.understanding_deployment == "qwen3:8b"
    assert config.qa_deployment == "qwen3:8b"
    assert config.cleaning_deployment == "qwen3:8b"
    assert config.execution_deployment == "qwen3:8b"


def test_config_honors_stage_specific_environment_overrides(monkeypatch):
    monkeypatch.setenv("SHEETHERO_DEPLOYMENT", "qwen3:8b")
    monkeypatch.setenv("SHEETHERO_EXECUTION_DEPLOYMENT", "qwen2.5-coder:7b-instruct")
    monkeypatch.setenv("SHEETHERO_QA_DEPLOYMENT", "qwen3:8b")

    config = Config()

    assert config.deployment == "qwen3:8b"
    assert config.execution_deployment == "qwen2.5-coder:7b-instruct"
    assert config.qa_deployment == "qwen3:8b"
    assert config.resolve_stage_deployment("execution") == "qwen2.5-coder:7b-instruct"
    assert config.resolve_stage_deployment("understanding") == "qwen3:8b"


def test_handle_llm_command_can_switch_execution_model_only():
    main_module = importlib.import_module("src.backend.main")
    config = Config()
    service = type("Service", (), {"config": config})()

    main_module._handle_llm_command(service, "!llm --switch--offline-execution qwen2.5-coder:7b-instruct")

    assert config.base_url == "http://localhost:11434/v1"
    assert config.execution_deployment == "qwen2.5-coder:7b-instruct"
    assert config.deployment != "qwen2.5-coder:7b-instruct"


def test_handle_llm_command_lists_offline_models(monkeypatch):
    main_module = importlib.import_module("src.backend.main")
    config = Config()
    service = type("Service", (), {"config": config})()

    monkeypatch.setattr(
        main_module,
        "_fetch_offline_model_names",
        lambda: ["qwen3:8b", "qwen2.5-coder:7b-instruct"],
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        main_module._handle_llm_command(service, "!llm --list-offline")

    output = buf.getvalue()
    assert "Available offline models:" in output
    assert "qwen3:8b" in output
    assert "qwen2.5-coder:7b-instruct" in output


def test_handle_llm_command_prompt_shows_numbered_models(monkeypatch):
    main_module = importlib.import_module("src.backend.main")
    config = Config()
    service = type("Service", (), {"config": config})()

    monkeypatch.setattr(
        main_module,
        "_fetch_offline_model_names",
        lambda: ["qwen3:8b", "qwen2.5-coder:7b-instruct"],
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt="": "2",
    )

    main_module._handle_llm_command(service, "!llm --switch--offline-execution")

    assert config.execution_deployment == "qwen2.5-coder:7b-instruct"


def test_sheethero_uses_split_stage_deployments(monkeypatch):
    from src.backend.agent.core import SheetHero as sheethero_module

    class _OpenAIStub:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(sheethero_module, "OpenAI", _OpenAIStub)

    config = Config(
        api_key="",
        base_url="http://localhost:11434/v1",
        deployment="qwen3:8b",
        execution_deployment="qwen2.5-coder:7b-instruct",
        qa_deployment="qwen3:8b",
        cleaning_deployment="qwen3:8b",
    )

    agent = sheethero_module.SheetHero(excel_paths=[], config=config, load_excel=False)

    assert agent.understanding_module.deployment == "qwen3:8b"
    assert agent.qa_stage.deployment == "qwen3:8b"
    assert agent.cleaning_module.deployment == "qwen3:8b"
    assert agent.execution_module.runner.deployment == "qwen2.5-coder:7b-instruct"
    assert config.api_key == ""


def test_find_latest_logger_uses_artifacts_loggers(tmp_path, monkeypatch):
    log_dir = tmp_path / "artifacts" / "loggers"
    log_dir.mkdir(parents=True)
    newer = log_dir / "sheethero_tc01_input01_20260409_140000.md"
    older = log_dir / "sheethero_tc01_input01_20260408_140000.md"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")

    monkeypatch.setattr(test_user_case, "PROJECT_ROOT", Path(tmp_path))

    latest = test_user_case.find_latest_logger_for_test(1)

    assert latest == newer


def test_extract_clarification_replies_from_conversations():
    task = {
        "conversations": [
            {"role": "user", "content": "initial request"},
            {"role": "assistant", "content": "question 1"},
            {"role": "user", "content": "answer 1"},
            {"role": "assistant", "content": "question 2"},
            {"role": "user", "content": "answer 2"},
        ]
    }

    replies = run_test.extract_clarification_replies(task)

    assert replies == ["answer 1", "answer 2"]


def test_extract_clarification_replies_ignores_initial_user_only():
    task = {
        "conversations": [
            {"role": "user", "content": "initial request"},
            {"role": "assistant", "content": "final result"},
        ]
    }

    replies = run_test.extract_clarification_replies(task)

    assert replies == []


def test_pick_clarification_reply_reuses_last_reply_when_needed():
    replies = ["treat missing values as zero"]

    first = run_test.pick_clarification_reply(replies, 0)
    second = run_test.pick_clarification_reply(replies, 1)
    third = run_test.pick_clarification_reply(replies, 2)

    assert first == "treat missing values as zero"
    assert second == "treat missing values as zero"
    assert third == "treat missing values as zero"


def test_pick_clarification_reply_none_when_no_replies_exist():
    assert run_test.pick_clarification_reply([], 0) is None
