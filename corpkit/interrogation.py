"""
corpkit: `Int`errogation and Interrogation-like classes
"""

from __future__ import print_function

from collections import OrderedDict
import pandas as pd
from corpkit.process import classname
from corpkit.lazyprop import lazyprop
from corpkit.process import make_record
from corpkit.constants import STRINGTYPE

def make_ser(row, k=False):
    return row['entry'].display(k)

class Interrogation(pd.DataFrame):
    """
    Stores results of a corpus interrogation, before or after editing. The main 
    attribute, :py:attr:`~corpkit.interrogation.Interrogation.results`, is a 
    Pandas object, which can be edited or plotted.
    """

    def __init__(self, data=None, corpus=None, query=None, norec=False, path=False):
        """Initialise the class"""
        if norec:
            super(Interrogation, self).__init__(data)
        else:
            super(Interrogation, self).__init__(make_record(data, corpus))
        
        self.query = query
        """`dict` containing values that generated the result"""
        self.corpus = corpus
        """The corpus interrogated"""
        self._concordance = None
        """Concordance lines last generated by self.conc()"""
        self._results = None
        """Table last generated by self.table()"""
        self.totals = len(self)
        """Number of results"""
        # a switch to show when data has been edited and views
        # not yet updated
        self._edited = False 
    
    def __str__(self):
        return "<%s instance: %s total>" % (classname(self), format(len(self), ','))

    def __repr__(self):
        return "<%s instance: %s total>" % (classname(self), format(len(self), ','))

    @lazyprop
    def results(self):
        if self._results is None or self._edited:
            return self.table()
        return self._results

    @lazyprop
    def concordance(self):
        if self._concordance is None or self._edited:
            return self.conc()
        return self._concordance

    def table(self, subcorpora='default', preserve_case=False, show=['w'], **kwargs):
        """
        Generate a result table view
        """
        import pandas as pd
        from corpkit.corpus import Corpus, Subcorpus

        # todo: fix this
        if subcorpora == 'default':
            subcorpora = 'file'
    
        from corpkit.interrogator import fix_show
        show = fix_show(show, 1)

        if not subcorpora:
            from collections import Counter
            ser = pd.Series(Counter([k.display(show) for k in self.data])).sort_values(ascending=False)
        else:
            df = self.copy()
            # should be apply
            df['entry'] = [x.display(show, preserve_case=preserve_case) for x in df['entry']]
            df['count'] = [1 for x in df.index]
            df = df.pivot_table(index=subcorpora, columns='entry', values='count', aggfunc=sum)
            df = df.fillna(0.0).astype(int)
            ser = df[df.sum().sort_values(ascending=False).index]
        self._results = ser
        self._edited = False
        return ser

    def conc(self, show=['w'], n=1000, shuffle=False, **kwargs):
        """
        Generate a concordance view
        """
        # n is num to show, because of slow loading!
        import pandas as pd
        from corpkit.interrogator import fix_show
        from corpkit.matches import _concer
        show = fix_show(show, 1)
        from corpkit.interrogation import Concordance
        rec = self.copy()
        if shuffle:
            import numpy as np
            rec = rec.reindex(np.random.permutation(rec.index))
        if n is not False:
            rec = rec[:n]
        dummy_ser = pd.Series([0 for i in rec.index])
        loc = list(rec.columns).index('entry')
        rec.insert(loc, 'l', [0 for i in rec.index])
        rec = rec.drop(['parse'], axis=1)
        rec.rename(columns={'entry':'m'}, inplace=True)
        clines = rec.apply(_concer, show=show, axis=1)
        cs = Concordance(clines)
        self._concordance = cs
        self._edited = False
        return cs

    def _just_or_skip(self, skip=False, entries={}, metadata={}, mode='any'):
        """Meta function for just or skip"""
        from corpkit.interrogator import fix_show_bit
        
        # to skip, we invert the matches with numpy
        if skip:
            import numpy as np
            func = np.invert
        else:
            # a dummy function
            func = lambda x: x
        
        rec = self.copy()
        if isinstance(entries, STRINGTYPE):
            entries = {'mw': entries}
        for k, v in entries.items():
            k = fix_show_bit(k)
            nk = '__' + k
            rec[nk] = rec.apply(make_ser, axis=1, k=[k])
            if isinstance(v, list):
                rec = rec[func(rec[nk].isin(v))]
            elif isinstance(v, STRINGTYPE):
                rec = rec[func(rec[nk].str.contains(v))]
            elif isinstance(v, int):
                rec = rec[func(rec[nk] == v)]
            rec = rec.drop(nk, axis=1)
        if isinstance(metadata, STRINGTYPE):
            metadata = {'mw': metadata}
        for k, v in metadata.items():
            if isinstance(v, list):
                rec = rec[func(rec[nk].isin(v))]
            elif isinstance(v, STRINGTYPE):
                rec = rec[func(rec[nk].str.contains(v))]
            elif isinstance(v, int):
                rec = rec[func(rec[nk] == v)]
            rec = rec.drop(nk, axis=1)
        self._edited = True
        return Interrogation(data=rec, corpus=self.corpus, query=self.query, norec=True)

    def just(self, entries={}, metadata={}, mode='any'):
        """
        Filter results from the interrogation
        """
        return self._just_or_skip(skip=False, entries=entries, metadata=metadata, mode=mode)

    def skip(self, entries={}, metadata={}, mode='any'):
        """
        Delete results from interrogation
        """
        return self._just_or_skip(skip=True, entries=entries, metadata=metadata, mode=mode)

    def edit(self, *args, **kwargs):
        """
        Manipulate results of interrogations.

        There are a few overall kinds of edit, most of which can be combined 
        into a single function call. It's useful to keep in mind that many are 
        basic wrappers around `pandas` operations---if you're comfortable with 
        `pandas` syntax, it may be faster at times to use its syntax instead.

        :Basic mathematical operations:

        First, you can do basic maths on results, optionally passing in some 
        data to serve as the denominator. Very commonly, you'll want to get 
        relative frequencies:

        :Example: 

        >>> data = corpus.interrogate({W: r'^t'})
        >>> rel = data.edit('%', SELF)
        >>> rel.results
            ..    to  that   the  then ...   toilet  tolerant  tolerate  ton
            01 18.50 14.65 14.44  6.20 ...     0.00      0.00      0.11 0.00
            02 24.10 14.34 13.73  8.80 ...     0.00      0.00      0.00 0.00
            03 17.31 18.01  9.97  7.62 ...     0.00      0.00      0.00 0.00

        For the operation, there are a number of possible values, each of 
        which is to be passed in as a `str`:

           `+`, `-`, `/`, `*`, `%`: self explanatory

           `k`: calculate keywords

           `a`: get distance metric
        
        `SELF` is a very useful shorthand denominator. When used, all editing 
        is performed on the data. The totals are then extracted from the edited 
        data, and used as denominator. If this is not the desired behaviour, 
        however, a more specific `interrogation.results` or 
        `interrogation.totals` attribute can be used.

        In the example above, `SELF` (or `'self'`) is equivalent to:

        :Example:

        >>> rel = data.edit('%', data.totals)

        :Keeping and skipping data:

        There are four keyword arguments that can be used to keep or skip rows 
        or columns in the data:

        * `just_entries`
        * `just_subcorpora`
        * `skip_entries`
        * `skip_subcorpora`

        Each can accept different input types:

        * `str`: treated as regular expression to match
        * `list`: 

          * of integers: indices to match
          * of strings: entries/subcorpora to match

        :Example:

        >>> data.edit(just_entries=r'^fr', 
        ...           skip_entries=['free','freedom'],
        ...           skip_subcorpora=r'[0-9]')

        :Merging data:

        There are also keyword arguments for merging entries and subcorpora:

        * `merge_entries`
        * `merge_subcorpora`

        These take a `dict`, with the new name as key and the criteria as 
        value. The criteria can be a str (regex) or wordlist.

        :Example:
        
        >>> from dictionaries.wordlists import wordlists
        >>> mer = {'Articles': ['the', 'an', 'a'], 'Modals': wordlists.modals}
        >>> data.edit(merge_entries=mer)

        :Sorting:

        The `sort_by` keyword argument takes a `str`, which represents the way 
        the result columns should be ordered.

        * `increase`: highest to lowest slope value
        * `decrease`: lowest to highest slope value
        * `turbulent`: most change in y axis values
        * `static`: least change in y axis values
        * `total/most`: largest number first
        * `infreq/least`: smallest number first
        * `name`: alphabetically

        :Example:

        >>> data.edit(sort_by='increase')

        :Editing text:
        
        Column labels, corresponding to individual interrogation results, can 
        also be edited with `replace_names`.

        :param replace_names: Edit result names, then merge duplicate entries
        :type replace_names: `str`/`list of tuples`/`dict`

        If `replace_names` is a string, it is treated as a regex to delete from 
        each name. If `replace_names` is a dict, the value is the regex, and 
        the key is the replacement text. Using a list of tuples in the form 
        `(find, replacement)` allows duplicate substitution values.

        :Example:

        >>> data.edit(replace_names={r'object': r'[di]obj'})

        :param replace_subcorpus_names: Edit subcorpus names, then merge duplicates.
                                        The same as `replace_names`, but on the other axis.
        :type replace_subcorpus_names: `str`/`list of tuples`/`dict`

        :Other options:

        There are many other miscellaneous options.

        :param keep_stats: Keep/drop stats values from dataframe after sorting
        :type keep_stats: `bool`
        
        :param keep_top: After sorting, remove all but the top *keep_top* results
        :type keep_top: `int`
        
        :param just_totals: Sum each column and work with sums
        :type just_totals: `bool`
        
        :param threshold: When using results list as dataframe 2, drop values 
                          occurring fewer than n times. If not keywording, you 
                          can use:
                                
           `'high'`: `denominator total / 2500`
           
           `'medium'`: `denominator total / 5000`
           
           `'low'`: `denominator total / 10000`
                            
           If keywording, there are smaller default thresholds

        :type threshold: `int`/`bool`

        :param span_subcorpora: If subcorpora are numerically named, span all 
                                from *int* to *int2*, inclusive
        :type span_subcorpora: `tuple` -- `(int, int2)`

        :param projection: multiply results in subcorpus by n
        :type projection: tuple -- `(subcorpus_name, n)`
        :param remove_above_p: Delete any result over `p`
        :type remove_above_p: `bool`

        :param p: set the p value
        :type p: `float`
        
        :param revert_year: When doing linear regression on years, turn annual 
                            subcorpora into 1, 2 ...
        :type revert_year: `bool`
        
        :param print_info: Print stuff to console showing what's being edited
        :type print_info: `bool`
        
        :param spelling: Convert/normalise spelling:
        :type spelling: `str` -- `'US'`/`'UK'`

        :Keywording options:

        If the operation is `k`, you're calculating keywords. In this case,
        some other keyword arguments have an effect:

        :param keyword_measure: what measure to use to calculate keywords:

           `ll`: log-likelihood
           `pd': percentage difference

        type keyword_measure: `str`
        
        :param selfdrop: When keywording, try to remove target corpus from 
                         reference corpus
        :type selfdrop: `bool`
        
        :param calc_all: When keywording, calculate words that appear in either 
                         corpus
        :type calc_all: `bool`

        :returns: :class:`corpkit.interrogation.Interrogation`
        """
        from corpkit.editor import editor
        return editor(self, *args, **kwargs)

    def sort(self, way, **kwargs):
        from corpkit.editor import editor
        return editor(self, sort_by=way, **kwargs)

    def visualise(self,
                  title='',
                  x_label=None,
                  y_label=None,
                  style='ggplot',
                  figsize=(8, 4),
                  save=False,
                  legend_pos='best',
                  reverse_legend='guess',
                  num_to_plot=7,
                  tex='try',
                  colours='Accent',
                  cumulative=False,
                  pie_legend=True,
                  rot=False,
                  partial_pie=False,
                  show_totals=False,
                  transparent=False,
                  output_format='png',
                  interactive=False,
                  black_and_white=False,
                  show_p_val=False,
                  indices=False,
                  transpose=False,
                  **kwargs
                 ):
        """Visualise corpus interrogations using `matplotlib`.

        :Example:

        >>> data.visualise('An example plot', kind='bar', save=True)
        <matplotlib figure>

        :param title: A title for the plot
        :type title: `str`
        :param x_label: A label for the x axis
        :type x_label: `str`
        :param y_label: A label for the y axis
        :type y_label: `str`
        :param kind: The kind of chart to make
        :type kind: `str` (`'line'`/`'bar'`/`'barh'`/`'pie'`/`'area'`/`'heatmap'`)
        :param style: Visual theme of plot
        :type style: `str` ('ggplot'/'bmh'/'fivethirtyeight'/'seaborn-talk'/etc)
        :param figsize: Size of plot
        :type figsize: `tuple` -- `(int, int)`
        :param save: If `bool`, save with *title* as name; if `str`, use `str` as name
        :type save: `bool`/`str`
        :param legend_pos: Where to place legend
        :type legend_pos: `str` ('upper right'/'outside right'/etc)
        :param reverse_legend: Reverse the order of the legend
        :type reverse_legend: `bool`
        :param num_to_plot: How many columns to plot
        :type num_to_plot: `int`/'all'
        :param tex: Use TeX to draw plot text
        :type tex: `bool`
        :param colours: Colourmap for lines/bars/slices
        :type colours: `str`
        :param cumulative: Plot values cumulatively
        :type cumulative: `bool`
        :param pie_legend: Show a legend for pie chart
        :type pie_legend: `bool`
        :param partial_pie: Allow plotting of pie slices only
        :type partial_pie: `bool`
        :param show_totals: Print sums in plot where possible
        :type show_totals: `str` -- 'legend'/'plot'/'both'
        :param transparent: Transparent .png background
        :type transparent: `bool`
        :param output_format: File format for saved image
        :type output_format: `str` -- 'png'/'pdf'
        :param black_and_white: Create black and white line styles
        :type black_and_white: `bool`
        :param show_p_val: Attempt to print p values in legend if contained in df
        :type show_p_val: `bool`
        :param indices: To use when plotting "distance from root"
        :type indices: `bool`
        :param stacked: When making bar chart, stack bars on top of one another
        :type stacked: `str`
        :param filled: For area and bar charts, make every column sum to 100
        :type filled: `str`
        :param legend: Show a legend
        :type legend: `bool`
        :param rot: Rotate x axis ticks by *rot* degrees
        :type rot: `int`
        :param subplots: Plot each column separately
        :type subplots: `bool`
        :param layout: Grid shape to use when *subplots* is True
        :type layout: `tuple` -- `(int, int)`
        :param interactive: Experimental interactive options
        :type interactive: `list` -- `[1, 2, 3]`
        :returns: matplotlib figure
        """
        from corpkit.plotter import plotter
        branch = kwargs.pop('branch', 'results')
        if branch.lower().startswith('r'):
            to_plot = self.results
        elif branch.lower().startswith('t'):
            to_plot = self.totals
        return plotter(to_plot,
                       title=title,
                       x_label=x_label,
                       y_label=y_label,
                       style=style,
                       figsize=figsize,
                       save=save,
                       legend_pos=legend_pos,
                       reverse_legend=reverse_legend,
                       num_to_plot=num_to_plot,
                       tex=tex,
                       rot=rot,
                       colours=colours,
                       cumulative=cumulative,
                       pie_legend=pie_legend,
                       partial_pie=partial_pie,
                       show_totals=show_totals,
                       transparent=transparent,
                       output_format=output_format,
                       interactive=interactive,
                       black_and_white=black_and_white,
                       show_p_val=show_p_val,
                       indices=indices,
                       transpose=transpose,
                       **kwargs
                      )

    def multiplot(self, leftdict={}, rightdict={}, **kwargs):
        from corpkit.plotter import multiplotter
        return multiplotter(self, leftdict=leftdict, rightdict=rightdict, **kwargs)

    def language_model(self, name, *args, **kwargs):
        """
        Make a language model from an Interrogation. This is usually done 
        directly on a :class:`corpkit.corpus.Corpus` object with the 
        :func:`~corpkit.corpus.Corpus.make_language_model` method.
        """
        from corpkit.model import _make_model_from_interro
        multi = self.multiindex()
        order = len(self.query['show'])
        return _make_model_from_interro(multi, name, order=order, *args, **kwargs)

    def save(self, savename, savedir='saved_interrogations', **kwargs):
        """
        Save an interrogation as pickle to ``savedir``.

        :Example:
        
        >>> o = corpus.interrogate(W, 'any')
        ### create ./saved_interrogations/savename.p
        >>> o.save('savename')
        
        :param savename: A name for the saved file
        :type savename: `str`
        
        :param savedir: Relative path to directory in which to save file
        :type savedir: `str`
        
        :param print_info: Show/hide stdout
        :type print_info: `bool`
        
        :returns: None
        """
        from corpkit.other import save
        save(self, savename, savedir=savedir, **kwargs)

    def quickview(self, n=25):
        """view top n results as painlessly as possible.

        :Example:
        
        >>> data.quickview(n=5)
            0: to    (n=2227)
            1: that  (n=2026)
            2: the   (n=1302)
            3: then  (n=857)
            4: think (n=676)

        :param n: Show top *n* results
        :type n: `int`
        :returns: `None`
        """
        from corpkit.other import quickview
        quickview(self, n=n)

    def tabview(self, **kwargs):
        import tabview
        import pandas as pd
        tabview.view(pd.DataFrame(self), **kwargs)

    def asciiplot(self,
                  row_or_col_name,
                  axis=0,
                  colours=True,
                  num_to_plot=100,
                  line_length=120,
                  min_graph_length=50,
                  separator_length=4,
                  multivalue=False,
                  human_readable='si',
                  graphsymbol='*',
                  float_format='{:,.2f}',
                  **kwargs):
        """
        A very quick ascii chart for result
        """
        from ascii_graph import Pyasciigraph
        from ascii_graph.colors import Gre, Yel, Red, Blu
        from ascii_graph.colordata import vcolor
        from ascii_graph.colordata import hcolor
        import pydoc

        graph = Pyasciigraph(
                            line_length=line_length,
                            min_graph_length=min_graph_length,
                            separator_length=separator_length,
                            multivalue=multivalue,
                            human_readable=human_readable,
                            graphsymbol=graphsymbol
                            )
        if axis == 0:
            dat = self.results.T[row_or_col_name]
        else:
            dat = self.results[row_or_col_name]
        data = list(zip(dat.index, dat.values))[:num_to_plot]
        if colours:
            pattern = [Gre, Yel, Red]
            data = vcolor(data, pattern)

        out = []
        for line in graph.graph(label=None, data=data, float_format=float_format):
            out.append(line)
        pydoc.pipepager('\n'.join(out), cmd='less -X -R -S')

    def rel(self, denominator='self', **kwargs):
        return self.edit('%', denominator, **kwargs)

    def keyness(self, measure='ll', denominator='self', **kwargs):
        return self.edit('k', denominator, **kwargs)

    def multiindex(self, indexnames=None):
        """Create a `pandas.MultiIndex` object from slash-separated results.

        :Example:

        >>> data = corpus.interrogate({W: 'st$'}, show=[L, F])
        >>> data.results
            ..  just/advmod  almost/advmod  last/amod 
            01           79             12          6 
            02          105              6          7 
            03           86             10          1 
        >>> data.multiindex().results
            Lemma       just almost last first   most 
            Function  advmod advmod amod  amod advmod 
            0             79     12    6     2      3 
            1            105      6    7     1      3 
            2             86     10    1     3      0                                   

        :param indexnames: provide custom names for the new index, or leave blank to guess.
        :type indexnames: `list` of strings

        :returns: :class:`corpkit.interrogation.Interrogation`, with 
                  `pandas.MultiIndex` as 
        :py:attr:`~corpkit.interrogation.Interrogation.results` attribute
        """

        from corpkit.other import make_multi
        return make_multi(self, indexnames=indexnames)

    def topwords(self, datatype='n', n=10, df=False, sort=True, precision=2):
        """Show top n results in each corpus alongside absolute or relative frequencies.

        :param datatype: show abs/rel frequencies, or keyness
        :type datatype: `str` (n/k/%)
        :param n: number of result to show
        :type n: `int`
        :param df: return a DataFrame
        :type df: `bool`
        :param sort: Sort results, or show as is
        :type sort: `bool`
        :param precision: float precision to show
        :type precision: `int`

        :Example:

        >>> data.topwords(n=5)
            1987           %   1988           %   1989           %   1990           %
            health     25.70   health     15.25   health     19.64   credit      9.22
            security    6.48   cancer     10.85   security    7.91   health      8.31
            cancer      6.19   heart       6.31   cancer      6.55   downside    5.46
            flight      4.45   breast      4.29   credit      4.08   inflation   3.37
            safety      3.49   security    3.94   safety      3.26   cancer      3.12

        :returns: None
        """
        from corpkit.other import topwords
        if df:
            return topwords(self, datatype=datatype, n=n, df=True,
                            sort=sort, precision=precision)
        else:
            topwords(self, datatype=datatype, n=n,
                     sort=sort, precision=precision)



    def perplexity(self):
        """
        Pythonification of the formal definition of perplexity.

        input:  a sequence of chances (any iterable will do)
        output: perplexity value.

        from https://github.com/zeffii/NLP_class_notes
        """

        def _perplex(chances):
            import math
            chances = [i for i in chances if i] 
            N = len(chances)
            product = 1
            for chance in chances:
                product *= chance
            return math.pow(product, -1/N)

        return self.results.apply(_perplex, axis=1)

    def entropy(self):
        """
        entropy(pos.edit(merge_entries=mergetags, sort_by='total').results.T
        """
        from scipy.stats import entropy
        import pandas as pd
        escores = entropy(self.rel().results.T)
        ser = pd.Series(escores, index=self.results.index)
        ser.name = 'Entropy'
        return ser

    def shannon(self):
        from corpkit.stats import shannon
        return shannon(self)

class Concordance(pd.core.frame.DataFrame):
    """
    A class for concordance lines, with methods for saving, formatting and editing.
    """
    
    def __init__(self, data):

        # recorder columns
        start = ['s', 'i', 'l', 'm', 'r']
        dfcols = [i for i in data.columns if i not in start]
        allcols = start + dfcols
        data = data[allcols]

        super(Concordance, self).__init__(data)
        self.concordance = data

    def format(self, kind='string', n=100, window=35,
               print_it=True, columns='all', metadata=True, **kwargs):
        """
        Print concordance lines nicely, to string, LaTeX or CSV

        :param kind: output format: `string`/`latex`/`csv`
        :type kind: `str`
        :param n: Print first `n` lines only
        :type n: `int`/`'all'`
        :param window: how many characters to show to left and right
        :type window: `int`
        :param columns: which columns to show
        :type columns: `list`

        :Example:

        >>> lines = corpus.concordance({T: r'/NN.?/ >># NP'}, show=L)
        ### show 25 characters either side, 4 lines, just text columns
        >>> lines.format(window=25, n=4, columns=[L,M,R])
            0                  we 're in  tucson     , then up north to flagst
            1  e 're in tucson , then up  north      to flagstaff , then we we
            2  tucson , then up north to  flagstaff  , then we went through th
            3   through the grand canyon  area       and then phoenix and i sp

        :returns: None
        """
        from corpkit.other import concprinter
        if print_it:
            print(concprinter(self, kind=kind, n=n, window=window,
                           columns=columns, return_it=True, metadata=metadata, **kwargs))
        else:
            return concprinter(self, kind=kind, n=n, window=window,
                           columns=columns, return_it=True, metadata=metadata, **kwargs)

    def calculate(self):
        """Make new Interrogation object from (modified) concordance lines"""
        from corpkit.process import interrogation_from_conclines
        return interrogation_from_conclines(self)

    def tabview(self, window=(55, 55), **kwargs):
        """Show concordance in interactive cli view"""
        from tabview import view
        import pandas as pd
        if isinstance(self.index, pd.MultiIndex):
            lsts = list(zip(*self.index.to_series()))
            widths = []
            for l in lsts:
                w = max([len(str(x)) for x in l])
                if w < 10:
                    widths.append(w)
                else:
                    widths.append(10)
        else:
            iwid = self.index.astype(str)[:100].str.len().max() + 1
            if iwid > 10:
                iwid = 10
            widths = [iwid]
        tot = len(self.columns) + len(self.index.names)
        aligns = [True] * tot
        truncs = [False] * tot
        if isinstance(window, int):
            window = [window, window]
        else:
            window = list(window)
        if window[0] > self['l'][:100].str.len().max():
            window[0] = self['l'][:100].str.len().max()
        if window[1] > self['r'][:100].str.len().max():
            window[1] = self['r'][:100].str.len().max()

        for i, c in enumerate(self.columns):
            if c == 'l':
                widths.append(window[0])
                truncs[i+len(self.index.names)] = True
            elif c == 'r':
                widths.append(window[1])
                aligns[i+len(self.index.names)] = False
            elif c == 'm':
                mx = self[c].astype(str)[:100].str.len().max() + 1
                if mx > 15:
                    mx = 15
                widths.append(mx)
                aligns[i+len(self.index.names)] = False         
            else:
                mx = self[c].astype(str)[:100].str.len().max() + 1
                if mx > 10:
                    mx = 10
                widths.append(mx)

        kwa = {'column_widths': widths, 'persist': True, 'trunc_left': truncs,
               'colours': kwargs.get('colours', False)}
        
        if 'align_right' not in kwargs:
            kwa['align_right'] = aligns

        view(pd.DataFrame(self), **kwa)

    def shuffle(self):
        """Shuffle concordance lines

        :param inplace: Modify current object, or create a new one
        :type inplace: `bool`

        :Example:

        >>> lines[:4].shuffle()
            3  01  1-01.txt.conll   through the grand canyon  area       and then phoenix and i sp
            1  01  1-01.txt.conll  e 're in tucson , then up  north      to flagstaff , then we we
            0  01  1-01.txt.conll                  we 're in  tucson     , then up north to flagst
            2  01  1-01.txt.conll  tucson , then up north to  flagstaff  , then we went through th

        """
        import random
        index = list(self.index)
        random.shuffle(index)
        shuffled = self.ix[index]
        shuffled.reset_index()
        return shuffled

    def edit(self, *args, **kwargs):
        """
        Delete or keep rows by subcorpus or by middle column text.

        >>> skipped = conc.edit(skip_entries=r'to_?match')
        """

        from corpkit.editor import editor
        return editor(self, *args, **kwargs)

    #def __str__(self):
    #    return self.format(print_it=False)

    #def __repr__(self):
    #    return self.format(print_it=False)

    def less(self, **kwargs):
        import pydoc
        pydoc.pipepager(self.format(print_it=False, **kwargs), cmd='less -X -R -S')
