"""
core/inference package
Automatic business rule inference and recommendation prototype.
"""
from core.inference.models import (
    InferredMandatoryField,
    InferredIdentityKey,
    InferredRulesResult,
)
from core.inference.rule_inferrer import (
    infer_mandatory_fields,
    infer_identity_keys,
    infer_rules_for_dataset,
)

__all__ = [
    "InferredMandatoryField",
    "InferredIdentityKey",
    "InferredRulesResult",
    "infer_mandatory_fields",
    "infer_identity_keys",
    "infer_rules_for_dataset",
]
