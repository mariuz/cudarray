from functools import reduce
import operator
import numpy as np

from .cudarray_wrap.array_data import ArrayData
import elementwise
import base


class CUDArray(object):
    def __init__(self, shape, dtype=None, np_data=None, array_data=None,
                 array_owner=None):
        shape = _require_iterable(shape)
        self.shape = shape
        self.transposed = False
        self.isbool = False
        if dtype is None:
            if np_data is None:
                dtype = np.dtype(base.float_)
            else:
                dtype = np_data.dtype
        if dtype == np.dtype('float64'):
            dtype = np.dtype(base.float_)
        elif dtype == np.dtype('int64'):
            dtype = np.dtype(base.int_)
        elif dtype == np.dtype('bool'):
            dtype = np.dtype(base.bool_)
            self.isbool = True
        if np_data is not None:
            np_data = np.require(np_data, dtype=dtype, requirements='C')
        if array_data is None:
            self._data = ArrayData(self.size, dtype, np_data)
        else:
            self._data = array_data

    def __array__(self):
        np_array = np.empty(self.shape, dtype=self.dtype)
        self._data.to_numpy(np_array)
        if self.isbool:
            np_array = np_array.astype(np.dtype('bool'))
        return np_array

    def __str__(self):
        return self.__array__().__str__()

    def __repr__(self):
        return self.__array__().__repr__()

    def _same_array(self, other):
        return self.data == other.data

    @property
    def data(self):
        return self._data.data

    @property
    def dtype(self):
        return self._data.dtype

    @property
    def itemsize(self):
        return self._data.dtype.itemsize

    @property
    def nbytes(self):
        return self.size*self.itemsize

    @property
    def ndim(self):
        return len(self.shape)

    @property
    def size(self):
        return _prod(self.shape)

    @property
    def T(self):
        return base.transpose(self)

    def view(self):
        return CUDArray(self.shape, self.dtype, None, self._data)

    def __len__(self):
        return self.shape[0]

    def __add__(self, other):
        return elementwise.add(self, other)

    def __radd__(self, other):
        return elementwise.add(self, other)

    def __iadd__(self, other):
        return elementwise.add(self, other, self)

    def __sub__(self, other):
        return elementwise.subtract(self, other)

    def __rsub__(self, other):
        return elementwise.subtract(self, other)

    def __isub__(self, other):
        return elementwise.subtract(self, other, self)

    def __mul__(self, other):
        return elementwise.multiply(self, other)

    def __rmul__(self, other):
        return elementwise.multiply(self, other)

    def __imul__(self, other):
        return elementwise.multiply(self, other, self)

    def __div__(self, other):
        return elementwise.divide(self, other)

    def __rdiv__(self, other):
        return elementwise.divide(self, other)

    def __idiv__(self, other):
        return elementwise.divide(self, other, self)

    def __pow__(self, other):
        return elementwise.power(self, other)

    def __rpow__(self, other):
        return elementwise.power(self, other)

    def __ipow__(self, other):
        return elementwise.power(self, other, self)

    def __eq__(self, other):
        return elementwise.equal(self, other)

    def __gt__(self, other):
        return elementwise.greater(self, other)

    def __ge__(self, other):
        return elementwise.greater_equal(self, other)

    def __lt__(self, other):
        return elementwise.less(self, other)

    def __le__(self, other):
        return elementwise.less_equal(self, other)

    def __ne__(self, other):
        return elementwise.not_equal(self, other)

    def __neg__(self):
        return elementwise.negative(self)

    def __ineg__(self):
        return elementwise.negative(self, self)

    def __getitem__(self, indices):
        if isinstance(indices, int):
            # Speedup case with a single index
            view_shape = self.shape[1:]
            view_size = _prod(view_shape)
            offset = indices * view_size
            data_view = ArrayData(view_size, self.dtype, owner=self._data,
                                  offset=offset)
            return CUDArray(view_shape, self.dtype, np_data=None,
                            array_data=data_view)

        # Standardize indices to a list of slices
        if len(indices) > len(self.shape):
            raise IndexError('too many indices for array')

        view_shape = []
        rest_must_be_contiguous = False
        offset = 0
        for i, dim in enumerate(self.shape):
            start = 0
            stop = dim
            append_dim = True
            if i < len(indices):
                idx = indices[i]
                if isinstance(idx, int):
                    append_dim = False
                    start = idx
                    stop = idx+1
                elif isinstance(idx, slice):
                    if idx.start is not None:
                        start = idx.start
                    if idx.stop is not None:
                        stop = idx.stop
                    if idx.step is not None:
                        raise NotImplementedError('only contiguous indices '
                                                  + 'are supported')
                elif idx is Ellipsis:
                    diff = self.ndim - len(indices)
                    indices = indices[:i] + [slice(None)]*diff + indices[i:]
                    return self[indices]
                else:
                    raise IndexError('only integers, slices and ellipsis are '
                                     + 'valid indices')

            view_dim = stop-start
            offset = offset * dim + start
            if append_dim:
                view_shape.append(view_dim)
            if rest_must_be_contiguous and view_dim > 1 and view_dim < dim:
                raise NotImplementedError('only contiguous indices are '
                                          + 'supported')
            if view_dim > 1:
                rest_must_be_contiguous = True

        view_shape = tuple(view_shape)
        view_size = _prod(view_shape)

        # Construct view
        data_view = ArrayData(view_size, self.dtype, owner=self._data,
                              offset=offset)
        return CUDArray(view_shape, self.dtype, np_data=None,
                        array_data=data_view)

    def __setitem__(self, indices, c):
        view = self.__getitem__(indices)
        base.copyto(view, c)


def _prod(x):
    return reduce(operator.mul, x, 1)


def _require_iterable(x):
    if hasattr(x, '__iter__'):
        return x
    else:
        return [x]
