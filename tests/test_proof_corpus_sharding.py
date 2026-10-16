"""Shard boundaries preserve every typed theorem and bound compilation units."""

import pytest

from tools.rational_proof_corpus import FAMILIES, generated_sources, proposition


def test_crossing_shard_boundary_neither_drops_nor_duplicates_theorems():
    sources, inventory = generated_sources(first_limit=21,second_limit=2)
    assert len(sources) == 2*len(FAMILIES)
    names = []
    for family in FAMILIES:
        first, second = inventory[family],inventory[family+'_part002']
        assert len(first) == 40
        assert len(second) == 2
        assert first[0]['name'].endswith('_01_01')
        assert first[-1]['name'].endswith('_20_02')
        assert second[0]['name'].endswith('_21_01')
        for label in (family,family+'_part002'):
            source = sources[label+'.lean']
            assert source.count('#print axioms ') == len(inventory[label])
            for row in inventory[label]:
                assert ('theorem '+row['name']+' ') in source
                names.append(row['name'])
    assert len(names) == len(set(names)) == 420


@pytest.mark.parametrize('first,second', [(0,1),(121,1),(1,0),(1,26),(True,1),(1,1.0)])
def test_invalid_dimensions_are_rejected(first,second):
    with pytest.raises(ValueError):
        generated_sources(first_limit=first,second_limit=second)


def test_new_upper_boundary_preserves_typed_domain_guards():
    statement = proposition('guarded_inverse',120,25)
    assert statement.variables == ('x',)
    assert any(predicate.relation == 'ne' for predicate in statement.domain)
    assert statement.content_id == proposition('guarded_inverse',120,25).content_id


@pytest.mark.parametrize('kwargs', [{'workers':0},{'workers':True},{'timeout':0},
                                    {'timeout':True},{'timeout':3601}])
def test_kernel_budgets_fail_before_creating_an_evidence_directory(tmp_path,kwargs):
    from tools.rational_proof_corpus import verify
    output=tmp_path/'evidence'
    with pytest.raises(ValueError):
        verify(output,**kwargs)
    assert not output.exists()
