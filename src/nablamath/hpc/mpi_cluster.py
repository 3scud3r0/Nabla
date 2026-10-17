"""Collective MPI mapping with per-rank receipts and uniform failure propagation."""
from ..calc.receipt import receipt


class MPICluster:
    def __init__(self, communicator=None):
        if communicator is None:
            try:
                from mpi4py import MPI
            except ImportError as exc:
                raise ImportError('Install nablamath[mpi] and an MPI runtime') from exc
            communicator = MPI.COMM_WORLD
        self.comm = communicator

    def map(self, function, items=None, *, operation, root=0):
        """All ranks call this; only root supplies items and receives the aggregate receipt."""
        rank, size = self.comm.Get_rank(), self.comm.Get_size()
        if type(root) is not int or not 0 <= root < size:
            raise ValueError('Invalid MPI root')
        shards, setup_error = None, None
        if rank == root:
            try:
                items = list(items)
                if not callable(function) or len(items) > 10000:
                    raise ValueError('Invalid MPI function or item budget')
                shards = [[(i,item) for i,item in enumerate(items) if i % size == worker] for worker in range(size)]
            except Exception as exc:
                setup_error = str(exc)
        setup_error = self.comm.bcast(setup_error,root=root)
        if setup_error:
            raise RuntimeError('MPI setup failed: '+setup_error)
        local = self.comm.scatter(shards,root=root)
        record, error = None, None
        try:
            result = [[i,function(item)] for i,item in local]
            record = receipt(operation,local,result,backend='mpi',metadata={'rank':rank,'size':size})
        except Exception as exc:
            error = str(exc)
        errors = self.comm.allgather(error)
        if any(e is not None for e in errors):
            raise RuntimeError('MPI worker failure: '+repr(errors))
        records = self.comm.gather(record,root=root)
        if rank != root:
            return None
        ordered = sorted((row for r in records for row in r['result']),key=lambda row:row[0])
        return receipt(operation,{'items':items},[row[1] for row in ordered],backend='mpi',
                       metadata={'size':size,'worker_receipts':records},parents=[r['content_id'] for r in records])
