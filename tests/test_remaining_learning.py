import pytest
from nablamath.core.semantic_ir import fingerprint
from nablamath.training.frontier_adapter import Consent, FrontierAdapter
from nablamath.training.reasoning_finetune import ReasoningProtocol, fit_reasoning, freeze_protocol
from nablamath.discovery.literature_search import CuratedSource, search_literature, record_literature_review
from nablamath.knowledge.literature import LiteratureCorpus, LiteratureEntry
from nablamath.documents.citations import Citation


def test_adapter_no_transport_without_consent():
    sent=[]; inputs={'question':'x+1'}
    consent=Consent('owner','provider','model-v1',(fingerprint(inputs),))
    adapter=FrontierAdapter(consent,transport=lambda *a,**k:sent.append(a),enabled=True)
    with pytest.raises(PermissionError):adapter.predict(inputs)
    assert sent==[]


def test_adapter_scoped_budget_and_receipts():
    inputs={'question':'x+1'}
    consent=Consent('owner','provider','model-v1',(fingerprint(inputs),),True)
    adapter=FrontierAdapter(consent,enabled=True,max_calls=1,transport=lambda data,**kw:{'answer':2})
    with pytest.raises(PermissionError):adapter.predict({'question':'secret'})
    assert adapter.receipts==[]
    assert adapter.predict(inputs)=={'answer':2}
    assert adapter.receipts[0]['status']=='completed'
    with pytest.raises(RuntimeError):adapter.predict(inputs)


def test_failed_transport_consumes_budget():
    x={'a':1}; consent=Consent('o','p','v',(fingerprint(x),),True)
    def fail(*a,**kw): raise OSError('offline')
    adapter=FrontierAdapter(consent,transport=fail,enabled=True,max_calls=1)
    with pytest.raises(OSError):adapter.predict(x)
    assert adapter.receipts[0]['status']=='failed'
    with pytest.raises(RuntimeError):adapter.predict(x)


def rows():
    return [{'id':str(i),'features':[i/10],'target':2*i/10+1,'split':'train'} for i in range(-10,11)]


def test_actual_supervised_fit_reduces_loss_reproducibly():
    data=rows(); p=freeze_protocol(data,owner='maintainer',epochs=1000,learning_rate=.1,l2=0)
    a=fit_reasoning(data,p); b=fit_reasoning(data,p)
    assert a==b and a.content_id==b.content_id
    assert a.losses[-1]<a.losses[0]*.000001
    assert a.predict([.7])==pytest.approx(2.4,abs=1e-6)
    with pytest.raises(ValueError):a.predict([1,2])


def test_fit_rejects_holdout_even_if_declared_in_manifest():
    data=rows(); data[0]['split']='test'
    p=freeze_protocol(data,owner='owner')
    with pytest.raises(ValueError):fit_reasoning(data,p)
    with pytest.raises(ValueError):fit_reasoning(rows(),ReasoningProtocol('owner',('other',),'0'*64))


@pytest.mark.parametrize('kwargs',[{'epochs':0},{'learning_rate':float('nan')},{'l2':-1},{'seed':True}])
def test_protocol_bounds(kwargs):
    with pytest.raises(ValueError):ReasoningProtocol('owner',('id',),'0'*64,**kwargs)


def corpus():
    return LiteratureCorpus((LiteratureEntry(Citation('NIST','Statistical reference datasets',('NIST',),1998,
        url='https://www.nist.gov/itl/sed/statistical-reference-datasets'),
        'Certified regression reference values',('regression','numerical'),'NIST supplied snapshot','declared-public-metadata'),),
        provenance='Test fixture metadata copied from public NIST source; not authenticated')


def test_curated_literature_query_tracks_source_and_false_positives():
    source=CuratedSource('NIST','https://www.nist.gov/itl/sed/statistical-reference-datasets','2026-10-15T00:00:00Z','curator',corpus())
    result=search_literature([source],'regression')
    assert result['sources'][0]['query']['hits'][0]['entry']['citation']['key']=='NIST'
    assert result['live_network_used'] is False
    review=record_literature_review(result,reviewer='declared reviewer',author='author',
         consulted_citation_keys=['NIST'],false_positive_keys=['NIST'],conclusion='inconclusive')
    assert review['false_positive_keys']==['NIST']
    assert review['global_novelty_established'] is False
    with pytest.raises(ValueError):
        record_literature_review(result,reviewer='author',author='author',consulted_citation_keys=[],false_positive_keys=[],conclusion='inconclusive')
    with pytest.raises(ValueError):
        record_literature_review(result,reviewer='r',author='a',consulted_citation_keys=['missing'],false_positive_keys=[],conclusion='inconclusive')


def test_source_contract_rejects_insecure_or_undated_snapshots():
    for url,date in [('http://example.org','2026-01-01T00:00:00Z'),('https://example.org','2026-01-01')]:
        with pytest.raises(ValueError):CuratedSource('source',url,date,'curator',corpus())


def test_frozen_protocol_binds_actual_features_and_targets():
    data=rows(); protocol=freeze_protocol(data,owner='owner')
    data[0]['target']=999
    with pytest.raises(ValueError,match='content differs'):fit_reasoning(data,protocol)


def test_protocol_refuses_nonfinite_response_before_receipt_success():
    inputs={'a':1}; consent=Consent('o','p','v',(fingerprint(inputs),),True)
    adapter=FrontierAdapter(consent,enabled=True,transport=lambda *a,**kw:float('nan'))
    with pytest.raises(ValueError):adapter.predict(inputs)
    assert adapter.receipts[0]['status']=='failed'


def test_receipts_are_detached_and_cannot_reset_inference_budget():
    inputs={'a':1}; consent=Consent('o','p','v',(fingerprint(inputs),),True)
    adapter=FrontierAdapter(consent,enabled=True,max_calls=1,transport=lambda *a,**kw:1)
    adapter.predict(inputs)
    receipt=adapter.receipts; receipt[0]['status']='forged'; receipt.clear()
    assert adapter.receipts[0]['status']=='completed'
    with pytest.raises(RuntimeError):adapter.predict(inputs)


def test_unbounded_inputs_stop_at_declared_limit():
    from itertools import repeat
    from nablamath.training.reasoning_finetune import _vector
    from nablamath.training.cross_domain_eval import TransferCase
    with pytest.raises(ValueError,match='Too many'):freeze_protocol(repeat({'id':'a'}),owner='owner')
    with pytest.raises(ValueError,match='Too many'):_vector(repeat(1))
    features=[1,2]; case=TransferCase('id','family','domain',features,3,'semantic')
    features[0]=99
    assert case.features==(1,2)
    with pytest.raises(ValueError,match='Typed'):search_literature([object()],'test')
