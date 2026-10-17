"""IPython catalog magic and observation tracing for ordinary trusted cells."""
import json
import shlex
from IPython.core.magic import Magics, magics_class, line_magic, cell_magic
from nablamath.calc import CalculationSession
from nablamath.calc.receipt import receipt


def _snapshot(value):
    if hasattr(value,'tolist'):
        value = value.tolist()
    # A JSON round trip detaches the audit record from mutable notebook values.
    return json.loads(json.dumps(value,allow_nan=False,sort_keys=True))


@magics_class
class NablaMagics(Magics):
    def _publish(self, record):
        namespace = self.shell.user_ns
        namespace.setdefault('_nabla_receipts',[]).append(record)
        namespace['_nabla_last_receipt'] = record
        return record

    @line_magic
    def nabla(self, line):
        """%nabla operation {"argument": value} executes the replayable catalog."""
        operation, _, raw = line.strip().partition(' ')
        if len(raw) > 100000:
            raise ValueError('Magic request exceeds budget')
        arguments = json.loads(raw or '{}')
        if not isinstance(arguments,dict):
            raise ValueError('Magic arguments must be a JSON object')
        return self._publish(CalculationSession().execute(operation,**arguments).to_data())

    @cell_magic
    def nabla_trace(self, line, cell):
        """%%nabla_trace name ... snapshots selected variables before and after a cell.

        This executes a normal IPython cell with normal notebook privileges.
        Names created by the cell may be listed too; missing inputs are recorded.
        """
        names = shlex.split(line)
        if len(cell) > 100000 or len(names) > 128 or any(not name.isidentifier() for name in names):
            raise ValueError('Invalid trace names or source budget')
        before = {name:_snapshot(self.shell.user_ns[name]) for name in names if name in self.shell.user_ns}
        execution = self.shell.run_cell(cell,store_history=False)
        if execution.error_before_exec or execution.error_in_exec:
            raise execution.error_before_exec or execution.error_in_exec
        after = {name:_snapshot(self.shell.user_ns[name]) for name in names if name in self.shell.user_ns}
        return self._publish(receipt('jupyter.cell',{'source':cell,'variables':before},
                                     {'variables':after,'value':_snapshot(execution.result)},backend='ipython',
                                     metadata={'traced_names':names,'limitations':'Selected values only; arbitrary cell replay is not guaranteed.'}))


def load_ipython_extension(ipython):
    ipython.register_magics(NablaMagics)


def unload_ipython_extension(ipython):
    ipython.magics_manager.magics['line'].pop('nabla',None)
    ipython.magics_manager.magics['cell'].pop('nabla_trace',None)
