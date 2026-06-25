from state import is_local_mutation_active, set_local_mutation
from state import _local_mutator


class TestLocalMutationState:
    def test_default_is_false(self):
        assert is_local_mutation_active() is False

    def test_set_true_works(self):
        set_local_mutation(True)
        assert is_local_mutation_active() is True

    def test_set_false_works(self):
        set_local_mutation(True)
        assert is_local_mutation_active() is True
        set_local_mutation(False)
        assert is_local_mutation_active() is False

    def test_default_after_reset(self):
        set_local_mutation(True)
        set_local_mutation(False)
        assert is_local_mutation_active() is False

    def test_isolation_between_tests(self):
        assert is_local_mutation_active() is False
