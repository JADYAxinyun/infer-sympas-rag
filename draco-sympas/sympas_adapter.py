"""Stable Agent-side SliceResult views; never recompute or upgrade SIL analysis."""
from copy import deepcopy

STATUSES = {'partial', 'complete', 'unsupported', 'failed', 'not_analyzed'}


class SymPasAdapter:
    def adapt(self, raw, number=1):
        if not isinstance(raw, dict):
            raw = {'analysis_status': 'failed', 'reason': 'invalid_slice_object'}
        raw = deepcopy(raw)
        declared = raw.get('analysis_status', raw.get('status', 'not_analyzed'))
        status = declared if isinstance(declared, str) and declared in STATUSES else 'not_analyzed'
        criterion = raw.get('criterion') or {}
        sources = raw.get('source_locations') or []
        calls = raw.get('call_chain') or []
        result = dict(raw, slice_id=f'slice-{number:03d}', status=status,
                      confidence=raw.get('precision', 'unknown'), raw_slice=raw,
                      criterion=criterion, nodes=sources, edges=calls,
                      procedures=sorted({raw.get('procedure', 'unknown')} | {call.get('callee', 'unknown') for call in calls}),
                      dependencies=dict(data=raw.get('data_dependencies', []),
                                        control=raw.get('control_dependencies', []), calls=calls))
        result['call_sites'] = [snapshot for snapshot in raw.get('instruction_slices', [])
                                if snapshot.get('instruction', {}).get('event') == 'call']
        if declared != status:
            result['adapter_warning'] = 'unrecognized_status'
        return result

    def read(self, normalized_infer):
        return [self.adapt(item, number) for number, item in enumerate(normalized_infer.get('slices', []), 1)]

    def status(self, results):
        states = {item['status'] for item in results}
        if 'partial' in states:
            return 'partial'
        if states == {'complete'}:
            return 'complete'
        for state in ('failed', 'unsupported', 'not_analyzed'):
            if state in states:
                return state
        return 'not_analyzed'
