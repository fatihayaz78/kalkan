"""Composition root: the one place where concrete adapters are chosen and wired (Dependency Injection)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..adapters.data.jsonl import JsonlDataSource
from ..adapters.registry.filesystem import FileSystemModelRegistry
from ..adapters.storage.sqlite import SqliteAuditLog, SqliteDatabase, SqliteFeedbackRepository
from ..application.engine import EngineProvider
from ..application.factory import PipelineFactory
from ..application.policies import ClientPolicies
from ..application.services import AdminService, GuardService
from ..application.training import ModelTrainer
from .auth import ApiKeyAuthenticator
from .settings import Settings


@dataclass
class Container:
    settings: Settings
    auth: ApiKeyAuthenticator
    engine: EngineProvider
    guard: GuardService
    admin: AdminService
    counts: Counter = field(default_factory=Counter)

    @classmethod
    def build(cls, s: Settings) -> "Container":
        registry = FileSystemModelRegistry(s.models_dir)
        factory = PipelineFactory()
        engine = EngineProvider(registry, factory)
        db = SqliteDatabase(s.db_path)
        audit, feedback = SqliteAuditLog(db, s.log_text), SqliteFeedbackRepository(db)
        trainer = ModelTrainer(registry, JsonlDataSource(s.data_dir), factory)
        return cls(
            settings=s,
            auth=ApiKeyAuthenticator(s.api_keys, s.admin_key),
            engine=engine,
            guard=GuardService(engine, audit, feedback, ClientPolicies(s.policies), s.max_chars, s.max_batch),
            admin=AdminService(engine, registry, trainer, audit, feedback),
        )
