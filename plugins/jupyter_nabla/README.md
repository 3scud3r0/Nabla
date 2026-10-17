# Jupyter Nabla

Install Nabla from the repository root, then install this plugin:

```bash
python -m pip install -e .
python -m pip install -e plugins/jupyter_nabla
```

In IPython or a Jupyter notebook:

```python
%load_ext jupyter_nabla
%nabla beta_binomial {"successes":2,"trials":3}
```

Trace selected variables in an ordinary trusted notebook cell:

```python
%%nabla_trace x y
x = 3
y = x*x
```

Receipts are stored in `_nabla_receipts`; the last receipt is also available as
`_nabla_last_receipt`. Cell tracing records the source and selected JSON-compatible
variables. It does not isolate Python execution or guarantee arbitrary cell replay.
