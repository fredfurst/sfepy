##
# 16.02.2005, c
import numpy as nm
import scipy as sc
import scipy.linalg as nla
import scipy.sparse as sp

import glob, re, time, sys, os
from copy import copy, deepcopy
from types import MethodType, UnboundMethodType
from getch import getch

import atexit

real_types = [nm.float64]
complex_types = [nm.complex128]

nm.set_printoptions( threshold = 100 )

sfepy_config_dir = os.path.expanduser('~/.sfepy')
if not os.path.exists(sfepy_config_dir):
    os.makedirs(sfepy_config_dir)

##
# 22.09.2005, c
# 24.10.2005
if sys.version[:5] < '2.4.0':
    def sorted( sequence ):
        tmp = copy( sequence )
        tmp.sort()
        return tmp

def get_debug():
    """
    Utility function providing ``debug()`` function.
    """
    old_excepthook = sys.excepthook

    try:
        from IPython.Debugger import Pdb
        from IPython.Shell import IPShell
        from IPython import ipapi

    except ImportError:
        debug = None

    else:
        def debug():
            shell = IPShell(argv=[''])
            sys.excepthook = old_excepthook
            ip = ipapi.get()
            def_colors = ip.options.colors
            Pdb(def_colors).set_trace(sys._getframe().f_back)

    if debug is None:
        import pdb
        debug = pdb.set_trace

    debug.__doc__ = """
    Start debugger on line where it is called, roughly equivalent to::

        import pdb; pdb.set_trace()

    First, this function tries to start an `IPython`-enabled
    debugger using the `IPython` API.

    When this fails, the plain old `pdb` is used instead.
    """

    return debug

debug = get_debug()

def mark_time(times, msg=None):
    """
    Time measurement utility.

    Measures times of execution between subsequent calls using
    time.clock(). The time is printed if the msg argument is not None.

    Examples
    --------

    >>> times = []
    >>> mark_time(times)
    ... do something
    >>> mark_time(times, 'elapsed')
    elapsed 0.1
    ... do something else
    >>> mark_time(times, 'elapsed again')
    elapsed again 0.05
    >>> times
    [0.10000000000000001, 0.050000000000000003]
    """
    tt = time.clock()
    times.append(tt)
    if (msg is not None) and (len(times) > 1):
        print msg, times[-1] - times[-2]

def import_file(filename, package_name=None):
    """
    Import a file as a module. The module is explicitly reloaded to
    prevent undesirable interactions.
    """
    path = os.path.dirname(filename)

    if not path in sys.path:
        sys.path.append( path )
        remove_path = True

    else:
        remove_path = False

    name = os.path.splitext(os.path.basename(filename))[0]

    if name in sys.modules:
        force_reload = True
    else:
        force_reload = False


    if package_name is not None:
        mod = __import__('.'.join((package_name, name)), fromlist=[name])

    else:
        mod = __import__(name)

    if force_reload:
        reload(mod)

    if remove_path:
        sys.path.pop(-1)

    return mod

def assert_( condition ):
    if not condition:
        raise ValueError( 'assertion failed!' )

##
# c: 06.04.2005, r: 05.05.2008
def pause( msg = None ):
    """
    Prints the line number and waits for a keypress.

    If you press:
    "q" ............. it will call sys.exit()
    any other key ... it will continue execution of the program

    This is useful for debugging.
    """
    f = sys._getframe(1)
    ff = f.f_code
    if (msg):
        print '%s, %d: %s(), %d: %s' % (ff.co_filename, ff.co_firstlineno,
                                        ff.co_name, f.f_lineno, msg)
    else:
        print '%s, %d: %s(), %d' % (ff.co_filename, ff.co_firstlineno,
                                    ff.co_name, f.f_lineno)
    spause()

##
# Silent pause.
# 18.02.2005, c
# 12.02.2007
def spause( msg = None ):
    """
    Waits for a keypress.

    If you press:
    "q" ............. it will call sys.exit()
    any other key ... it will continue execution of the program

    This is useful for debugging. This function is called from pause().
    """
    if (msg):
        print msg
    sys.stdout.flush()
    ch = getch()
    if ch == 'q':
        sys.exit()

##
# 02.01.2005
class Struct( object ):
    # 03.10.2005, c
    # 26.10.2005
    def __init__( self, **kwargs ):
        if kwargs:
            self.__dict__.update( kwargs )
        
    # 08.03.2005
    def __str__(self):
        """Print instance class, name and items in alphabetical order.

        If the class instance has '_str_attrs' attribute, only the attributes
        listed there are taken into account. Other attributes are provided only
        as a list of attribute names (no values).

        For attributes that are Struct instances, if
        the listed attribute name ends with '.', the attribute is printed fully
        by calling str(). Otherwise only its class name/name are printed.
        """
        ss = "%s" % self.__class__.__name__
        if hasattr( self, 'name' ):
            ss += ":%s" % self.name
        ss += '\n'

        keys = self.__dict__.keys()
        str_attrs = sorted(self.get_default_attr('_str_attrs',
                                                 keys))
        printed_keys = []
        for key in str_attrs:
            if key[-1] == '.':
                key = key[:-1]
                full_print = True
            else:
                full_print = False

            printed_keys.append(key)

            try:
                val = self.__dict__[key]
            except KeyError:
                continue

            if (not full_print) and issubclass( val.__class__, Struct ):
                ss += "  %s:\n    %s" % (key, val.__class__.__name__)
                if hasattr( val, 'name' ):
                    ss += ":%s" % val.name
                ss += '\n'
            else:
                aux = "\n" + str( val )
                aux = aux.replace( "\n", "\n    " );
                ss += "  %s:\n%s\n" % (key, aux[1:])

        other_keys = sorted(set(keys).difference(set(printed_keys)))
        if len(other_keys):
            ss += "  other attributes:\n    %s\n" \
                  % '\n    '.join(key for key in other_keys)

        return( ss.rstrip() )

    def __repr__( self ):
        ss = "%s" % self.__class__.__name__
        if hasattr( self, 'name' ):
            ss += ":%s" % self.name
        return ss

    ##
    # 28.08.2007, c
    def __add__( self, other ):
        """Merge Structs. Attributes of new are those of self unless an
        attribute and its counterpart in other are both Structs - these are
        merged then."""
        new = copy( self )
        for key, val in other.__dict__.iteritems():
            if hasattr( new, key ):
                sval = getattr( self, key )
                if issubclass( sval.__class__, Struct ) and \
                       issubclass( val.__class__, Struct ):
                    setattr( new, key, sval + val )
                else:
                    setattr( new, key, sval )
            else:
                setattr( new, key, val )
        return new

    ##
    # 28.08.2007, c
    def __iadd__( self, other ):
        """Merge Structs in place. Attributes of self are left unchanged
        unless an attribute and its counterpart in other are both Structs -
        these are merged then."""
        for key, val in other.__dict__.iteritems():
            if hasattr( self, key ):
                sval = getattr( self, key )
                if issubclass( sval.__class__, Struct ) and \
                       issubclass( val.__class__, Struct ):
                    setattr( self, key, sval + val )
            else:
                setattr( self, key, val )
        return self

    # 08.03.2005, c
    def str_all( self ):
        ss = "%s\n" % self.__class__
        for key, val in self.__dict__.iteritems():
            if issubclass( self.__dict__[key].__class__, Struct ):
                ss += "  %s:\n" % key
                aux = "\n" + self.__dict__[key].str_all()
                aux = aux.replace( "\n", "\n    " );
                ss += aux[1:] + "\n"
            else:
                aux = "\n" + str( val )
                aux = aux.replace( "\n", "\n    " );
                ss += "  %s:\n%s\n" % (key, aux[1:])
        return( ss.rstrip() )

    ##
    # 09.07.2007, c
    def to_dict( self ):
        return copy( self.__dict__ )

    def get(self, key, default):
        """A dict-like get for Struct attributes."""
        return self.__dict__.get(key, default)

    def get_default_attr( self, key, default = None, msg_if_none = None ):
        """Behaves like dict.get() if msg_if_none is None."""
        return get_default_attr( self, key, default, msg_if_none )

    def set_default_attr( self, key, default = None ):
        """Behaves like dict.setdefault()."""
        return self.__dict__.setdefault( key, default )

    def copy(self, deep=False, name=None):
        """Make a (deep) copy of self.

        Parameters:

        deep : bool
            Make a deep copy.
        name : str
            Name of the copy, with default self.name + '_copy'.
        """
        if deep:
            other = deepcopy(self)
        else:
            other = copy(self)

        if hasattr(self, 'name'):
            other.name = get_default(name, self.name + '_copy')

        return other
#
# 12.07.2007, c
class IndexedStruct( Struct ):

    ##
    # 12.07.2007, c
    def __getitem__( self, key ):
        return getattr( self, key )

    ##
    # 12.07.2007, c
    def __setitem__( self, key, val ):
        setattr( self, key, val )

##
# 14.07.2006, c
class Container( Struct ):

    def __init__( self, objs = None, **kwargs ):
        Struct.__init__( self, **kwargs )

        if objs is not None:
            self._objs = objs
            self.update()
        else:
            self._objs = []
            self.names = []

    def update( self, objs = None ):
        if objs is not None:
            self._objs = objs

        self.names = [obj.name for obj in self._objs]

    def __setitem__(self, ii, obj):
        try:
            if isinstance(ii, str):
                if ii in self.names:
                    ii = self.names.index(ii)
                else:
                    ii = len(self.names)

            elif not isinstance(ii, int):
                    raise ValueError('bad index type! (%s)' % type(ii))

            if ii >= len(self.names):
                self.append(obj)

            else:
                self._objs[ii] = obj
                self.names[ii] = obj.name

        except (IndexError, ValueError), msg:
            raise IndexError(msg)

    def __getitem__(self, ii):
        try:
            if isinstance(ii, str):
                ii = self.names.index(ii)
            elif not isinstance( ii, int ):
                raise ValueError('bad index type! (%s)' % type(ii))

            return  self._objs[ii]

        except (IndexError, ValueError), msg:
            raise IndexError(msg)

    def __iter__( self ):
        return self._objs.__iter__()

    ##
    # 18.07.2006, c
    def __len__( self ):
        return len( self._objs )

    def insert(self, ii, obj):
        self._objs.insert(ii, obj)
        self.names.insert(ii, obj.name)

    def append( self, obj ):
        self._objs.append( obj )
        self.names.append( obj.name )

    def get(self, ii, default=None, msg_if_none=None):
        """
        Get an item from Container - a wrapper around
        Container.__getitem__() with defaults and custom error message.

        Parameters
        ----------
        ii : int or str
            The index or name of the item.
        default : any, optional
            The default value returned in case the item `ii` does not exist.
        msg_if_none : str, optional
            If not None, and if `default` is None and the item `ii` does
            not exist, raise ValueError with this message.
        """
        try:
            out = self[ii]

        except (IndexError, ValueError):
            if default is not None:
                out = default

            else:
                if msg_if_none is not None:
                    raise ValueError(msg_if_none)

                else:
                    raise

        return out

    def remove_name( self, name ):
        ii = self.names.index[name]
        del self.names[ii]
        del self._objs[ii]

    ##
    # dict-like methods.
    def itervalues( self ):
        return self._objs.__iter__()

    def iterkeys( self ):
        return self.get_names().__iter__()

    def iteritems( self ):
        for obj in self._objs:
            yield obj.name, obj

    ##
    # 20.09.2006, c
    def has_key( self, ii ):
        if isinstance( ii, int ):
            if (ii < len( self )) and (ii >= (-len( self ))):
                return True
            else:
                return False
        elif isinstance( ii, str ):
            try:
                self.names.index( ii )
                return True
            except:
                return False
        else:
            raise IndexError, 'unsupported index type: %s' % key
        
    ##
    # 12.06.2007, c
    def print_names( self ):
        print [obj.name for obj in self._objs]

    def get_names( self ):
        return [obj.name for obj in self._objs]

    def as_dict(self):
        """
        Return stored objects in a dictionary with object names as keys.
        """
        out = {}
        for key, val in self.iteritems():
            out[key] = val

        return out

##
# 30.11.2004, c
# 01.12.2004
# 01.12.2004
class OneTypeList( list ):
    def __init__( self, item_class ):
        self.item_class = item_class
        pass
    
    def __setitem__( self, key, value ):
        if (type( value ) in (list, tuple)):
            for ii, val in enumerate( value ):
                if not isinstance(val, self.item_class):
                    raise TypeError
        else:
            if not isinstance(value, self.item_class):
                raise TypeError
        list.__setitem__( self, key, value )

    ##
    # 21.11.2005, c
    def __getitem__( self, ii ):
        if isinstance( ii, int ):
            return list.__getitem__( self, ii )
        elif isinstance( ii, str ):
            ir = self.find( ii, ret_indx = True )
            if ir:
                return list.__getitem__( self, ir[0] )
            else:
                raise IndexError, ii
        else:
            raise IndexError, ii
    

    def __str__( self ):
        ss = "[\n"
        for ii in self:
            aux = "\n" + ii.__str__()
            aux = aux.replace( "\n", "\n  " );
            ss += aux[1:] + "\n"
        ss += "]"
        return( ss )
    
    def find( self, name, ret_indx = False ):
        for ii, item in enumerate( self ):
            if item.name == name:
                if ret_indx:
                    return ii, item
                else:
                    return item
        return None

    ##
    # 12.06.2007, c
    def print_names( self ):
        print [ii.name for ii in self]

    def get_names( self ):
        return [ii.name for ii in self]

class Output(Struct):
    """
    Factory class providing output (print) functions. All SfePy
    printing should be accomplished by this class.

    Examples
    --------
    >>> from sfepy.base.base import Output
    >>> output = Output('sfepy:')
    >>> output(1, 2, 3, 'hello')
    sfepy: 1 2 3 hello
    >>> output.prefix = 'my_cool_app:'
    >>> output(1, 2, 3, 'hello')
    my_cool_app: 1 2 3 hello
    """

    def __init__(self, prefix, filename=None, combined=False, **kwargs):
        Struct.__init__(self, **kwargs)

        self.prefix = prefix

        self.set_output(filename, combined)
        
    def __call__(self, *argc, **argv):
        """Call self.output_function.

        Parameters
        ----------
        argc : positional arguments
            The values to print.
        argv : keyword arguments
            The arguments to control the output behaviour. Supported keywords
            are listed below.
        verbose : bool (in **argv)
            No output if False.
        """
        verbose = argv.get('verbose', True)
        if verbose:
            self.output_function(*argc, **argv)

    def set_output(self, filename=None, quiet=False, combined=False,
                   append=False):
        """
        Set the output mode.

        If `quiet` is `True`, no messages are printed to screen. If
        simultaneously `filename` is not `None`, the messages are logged
        into the specified file.

        If `quiet` is `False`, more combinations are possible. If
        `filename` is `None`, output is to screen only, otherwise it is
        to the specified file. Moreover, if `combined` is `True`, both
        the ways are used.

        Parameters
        ----------
        filename : str
            Print messages into the specified file.
        quiet : bool
            Do not print anything to screen.
        combined : bool
            Print both on screen and into the specified file.
        append : bool
            Append to an existing file instead of overwriting it. Use with
            `filename`.
        """
        self.level = 0
        def output_none(*argc, **argv):
            pass

        def output_screen(*argc, **argv):
            format = '%s' + ' %s' * (len(argc) - 1)
            msg =  format % argc

            if msg.startswith('...'):
                self.level -= 1

            print self._prefix + ('  ' * self.level) + msg

            if msg.endswith('...'):
                self.level += 1

        def output_file(*argc, **argv):
            format = '%s' + ' %s' * (len(argc) - 1)
            msg =  format % argc

            if msg.startswith('...'):
                self.level -= 1

            fd = open(filename, 'a')
            print >>fd, self._prefix + ('  ' * self.level) + msg
            fd.close()

            if msg.endswith('...'):
                self.level += 1

        def output_combined(*argc, **argv):
            format = '%s' + ' %s' * (len(argc) - 1)
            msg =  format % argc

            if msg.startswith('...'):
                self.level -= 1

            print self._prefix + ('  ' * self.level) + msg

            fd = open(filename, 'a')
            print >>fd, self._prefix + ('  ' * self.level) + msg
            fd.close()

            if msg.endswith('...'):
                self.level += 1

        def reset_file(filename):
            output_dir = os.path.dirname(filename)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            fd = open( filename, 'w' )
            fd.close()

        if quiet is True:
            if filename is not None:
                if not append:
                    reset_file(filename)

                self.output_function = output_file

            else:
                self.output_function = output_none


        else:
            if filename is None:
                self.output_function = output_screen

            else:
                if not append:
                    reset_file(filename)

                if combined:
                    self.output_function = output_combined

                else:
                    self.output_function = output_file

    def get_output_function(self):
        return self.output_function

    def set_output_prefix(self, prefix):
        assert_(isinstance(prefix, str))
        if len(prefix) > 0:
            prefix += ' '
        self._prefix = prefix
        
    def get_output_prefix(self):
        return self._prefix[:-1]
    prefix = property(get_output_prefix, set_output_prefix)
    
output = Output('sfepy:')

def print_structs(objs):
    """Print Struct instances in a container, works recursively. Debugging
    utility function."""
    if isinstance(objs, dict):
        for key, vals in objs.iteritems():
            print key
            print_structs(vals)
    elif isinstance(objs, list):
        for vals in objs:
            print_structs(vals)
    else:
        print objs

def iter_dict_of_lists(dol, return_keys=False):
    for key, vals in dol.iteritems():
        for ii, val in enumerate(vals):
            if return_keys:
                yield key, ii, val
            else:
                yield val

##
# 19.07.2005, c
# 26.05.2006
# 17.10.2007
def dict_to_struct( *args, **kwargs ):
    """Convert a dict instance to a Struct instance."""
    try:
        level = kwargs['level']
    except:
        level = 0
        
    try:
        flag = kwargs['flag']
    except:
        flag = (1,)

    # For level 0 only...
    try:
        constructor = kwargs['constructor']
    except:
        constructor = Struct

    out = []
    for arg in args:
        if type( arg ) == dict:
            if flag[level]:
                aux = constructor()
            else:
                aux = {}
                
            for key, val in arg.iteritems():
                if type( val ) == dict:
                    try:
                        flag[level+1]
                    except:
                        flag = flag + (0,)
                    val2 = dict_to_struct( val, level = level + 1, flag = flag )
                    if flag[level]:
                        aux.__dict__[key] = val2
                    else:
                        aux[key] = val2
                else:
                    if flag[level]:
                        aux.__dict__[key] = val
                    else:
                        aux[key] = val
            out.append( aux )
        else:
            out.append( arg )

    if len( out ) == 1:
        out = out[0]

    return out

##
# 23.01.2006, c
def is_sequence( var ):
    if issubclass( var.__class__, tuple ) or issubclass( var.__class__, list ):
        return True
    else:
        return False

##
# 17.10.2007, c
def is_derived_class( cls, parent ):
    return issubclass( cls, parent ) and (cls is not parent)

##
# 23.10.2007, c
def insert_static_method( cls, function ):
    setattr( cls, function.__name__, staticmethod( function ) )

##
# 23.10.2007, c
def insert_method( instance, function ):
    setattr( instance, function.__name__,
             UnboundMethodType( function, instance, instance.__class__ ) )

def use_method_with_name( instance, method, new_name ):
    setattr( instance, new_name, method )

def insert_as_static_method( cls, name, function ):
    setattr( cls, name, staticmethod( function ) )

def find_subclasses(context, classes, omit_unnamed=False):
    """Find subclasses of the given classes in the given context.

    Examples
    --------

    >>> solver_table = find_subclasses(vars().items(),
                                       [LinearSolver, NonlinearSolver,
                                        TimeSteppingSolver, EigenvalueSolver,
                                        OptimizationSolver])
    """
    var_dict = context.items()
    table = {}

    for key, var in var_dict:
        try:
            for cls in classes:
                if is_derived_class(var, cls):
                    if hasattr(var, 'name'):
                        key = var.name
                        if omit_unnamed and not key:
                            continue
                    else:
                        key = var.__class__.__name__

                    table[key] = var
                    break

        except TypeError:
            pass
    return table

def load_classes(filenames, classes, package_name=None):
    """
    For each filename in filenames, load all subclasses of classes listed.
    """
    table = {}
    for filename in filenames:
        mod = import_file(filename, package_name=package_name)
        table.update(find_subclasses(vars(mod), classes, omit_unnamed=True))

    return table

##
# 09.08.2006, c
def invert_dict( d, is_val_tuple = False ):
    di = {}
    for key, val in d.iteritems():
        if is_val_tuple:
            for v in val:
                di[v] = key
        else:
            di[val] = key
    return di

def remap_dict(d, map):
    """
    Utility function to remap state dict keys according to var_map.
    """
    out = {}
    for new_key, key in map.iteritems():
        out[new_key] = d[key]

    return out

##
# 24.08.2006, c
# 05.09.2006
def dict_from_keys_init( keys, seq_class = None ):

    if seq_class is None:
        return {}.fromkeys( keys )
    
    out = {}
    for key in keys:
        out[key] = seq_class()
    return out

##
# 16.10.2006, c
def dict_extend( d1, d2 ):
    for key, val in d1.iteritems():
        val.extend( d2[key] )

def set_defaults( dict_, defaults ):
    for key, val in defaults.iteritems():
        dict_.setdefault( key, val )

##
# c: 12.03.2007, r: 04.04.2008
def get_default( arg, default, msg_if_none = None ):
    
    if arg is None:
        out = default
    else:
        out = arg

    if (out is None) and (msg_if_none is not None):
        raise ValueError( msg_if_none )

    return out

##
# c: 28.04.2008, r: 28.04.2008
def get_default_attr( obj, attr, default, msg_if_none = None ):
    if hasattr( obj, attr ):
        out = getattr( obj, attr )
    else:
        out = default

    if (out is None) and (msg_if_none is not None):
        raise ValueError( msg_if_none )

    return out

def get_arguments(omit=None):
    """Get a calling function's arguments.

    Returns:

    args : dict
        The calling function's  arguments.
    """
    from inspect import getargvalues, stack
    if omit is None:
        omit = []

    _args, _, _, _vars = getargvalues(stack()[1][0])

    args = {}
    for name in _args:
        if name in omit: continue
        args[name] = _vars[name]

    return args

def check_names(names1, names2, msg):
    """Check if all names in names1 are in names2, otherwise raise IndexError
    with the provided message msg.
    """
    names = set(names1)
    both = names.intersection(names2)
    if both != names:
        missing = ', '.join(ii for ii in names.difference(both))
        raise IndexError(msg % missing)

##
# c: 27.02.2008, r: 27.02.2008
def select_by_names( objs_all, names, replace = None, simple = True ):
    objs = {}
    for key, val in objs_all.iteritems():
        if val.name in names:
            if replace is None:
                objs[key] = val
            else:
                new_val = copy( val )
                old_attr = getattr( val, replace[0] )
                if simple:
                    new_attr = old_attr % replace[1]
                    setattr( new_val, replace[0], new_attr )
                else:
                    new_attr = replace[1].get( val.name, old_attr )
                    setattr( new_val, replace[0], new_attr )
                objs[key] = new_val
    return objs

def ordered_iteritems(adict):
    keys = adict.keys()
    order = nm.argsort(keys)
    for ii in order:
        key = keys[ii]
        yield key, adict[key]
