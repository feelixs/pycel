# -*- coding: UTF-8 -*-
#
# Copyright 2011-2019 by Dirk Gorissen, Stephen Rauch and Contributors
# All rights reserved.
# This file is part of the Pycel Library, Licensed under GPLv3 (the 'License')
# You may not use this work except in compliance with the License.
# You may obtain a copy of the Licence at:
#   https://www.gnu.org/licenses/gpl-3.0.en.html

"""
Python equivalents of Lookup and Reference library functions
"""
from bisect import bisect_right

import numpy as np

from pycel.excelutil import (
    AddressCell,
    AddressRange,
    build_wildcard_re,
    ERROR_CODES,
    ExcelCmp,
    flatten,
    is_address,
    list_like,
    MAX_COL,
    MAX_ROW,
    NA_ERROR,
    REF_ERROR,
    VALUE_ERROR,
)
from pycel.lib.function_helpers import (
    excel_helper,
)


""" Functions consuming or producing references.
INDEX() - Takes an array or reference, returns the value pointed to
OFFSET()  - Takes a reference, returns a reference
INDIRECT() - Returns the reference specified by a text string.
ROW() - Takes a reference, returns row number
COLUMN() - Takes a reference, returns column number

All of these can cause problems when compiling the workbook.

OFFSET() and INDIRECT() should generally be avoided, as they can cause
performance problems in any large spreadsheet.  That is because the
outputs are volatile.  When compiling, this means they are not necessarily
known when the sheet is compiled.  In general use INDEX() instead of
OFFSET(), and don't use INDIRECT() at all, if needing to compile the workbook.

As a general reminder, all of these functions are volatile and can
cause performance problems in large spreadsheets because of frequent
need to recalc.

OFFSET()
INDIRECT()
ROWS()
COLUMNS()
CELL()
NOW()
TODAY()
"""


def _match(lookup_value, lookup_array, match_type=1):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   MATCH-function-E8DFFD45-C762-47D6-BF89-533F4A37673A

    """ The relative position of a specified item in a range of cells.

    Match_type Behavior

    1: return the largest value that is less than or equal to
    `lookup_value`. `lookup_array` must be in ascending order.

    0: return the first value that is exactly equal to lookup_value.
    `lookup_array` can be in any order.

    -1: return the smallest value that is greater than or equal to
    `lookup_value`. `lookup_array` must be in descending order.

    If `match_type` is 0 and lookup_value is a text string, you can use the
    wildcard characters — the question mark (?) and asterisk (*).

    :param lookup_value: value to match (value or cell reference)
    :param lookup_array: range of cells being searched.
    :param match_type: The number -1, 0, or 1.
    :return: #N/A if not found, or relative position in `lookup_array`
    """
    lookup_value = ExcelCmp(lookup_value)

    if match_type == 1:
        # Use a binary search to speed it up.  Excel seems to do this as it
        # would explain the results seen when doing out of order searches.
        lo = 0
        while lo < len(lookup_array) and lookup_array[lo] is None:
            lo += 1

        hi = len(lookup_array)
        while hi > 0 and lookup_array[hi - 1] is None:
            hi -= 1

        result = bisect_right(lookup_array, lookup_value, lo=lo, hi=hi)
        while result and lookup_value.cmp_type != ExcelCmp(
                lookup_array[result - 1]).cmp_type:
            result -= 1
        if result == 0 or lookup_array[result - 1] is None:
            result = NA_ERROR
        return result

    result = [NA_ERROR]

    if match_type == 0:
        def compare(idx, val):
            if val == lookup_value:
                result[0] = idx
                return True

        if lookup_value.cmp_type == 1:
            # string matches might be wildcards
            re_compare = build_wildcard_re(lookup_value.value)
            if re_compare is not None:
                def compare(idx, val):  # noqa: F811
                    if re_compare(val.value):
                        result[0] = idx
                        return True
    else:
        def compare(idx, val):
            if val < lookup_value:
                return True
            result[0] = idx
            return val == lookup_value

    for i, value in enumerate(lookup_array, 1):
        if value not in ERROR_CODES:
            value = ExcelCmp(value)
            if value.cmp_type == lookup_value.cmp_type and compare(i, value):
                break

    return result[0]


# def address(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   address-function-d0c26c0d-3991-446b-8de4-ab46431d4f89


# def areas(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   areas-function-8392ba32-7a41-43b3-96b0-3695d2ec6152


@excel_helper(cse_params=0, number_params=0, err_str_params=0)
def choose(index, *args):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   choose-function-fc5c184f-cb62-4ec7-a46e-38653b98f5bc
    index = int(index)
    if index < 1 or len(args) < index or not args:
        return VALUE_ERROR
    return args[index - 1]


@excel_helper(ref_params=0)
def column(ref):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   COLUMN-function-44E8C754-711C-4DF3-9DA4-47A55042554B
    if ref.is_range:
        if ref.end.col_idx == 0:
            return range(1, MAX_COL + 1)
        else:
            return (tuple(range(ref.start.col_idx, ref.end.col_idx + 1)), )
    else:
        return ref.col_idx


# def columns(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   columns-function-4e8e7b4e-e603-43e8-b177-956088fa48ca


# def filter(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   filter-function-f4f7cb66-82eb-4767-8f7c-4877ad80c759


# def formulatext(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   formulatext-function-0a786771-54fd-4ae2-96ee-09cda35439c8


# def getpivotdata(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   getpivotdata-function-8c083b99-a922-4ca0-af5e-3af55960761f


@excel_helper(cse_params=0, bool_params=3, number_params=2, err_str_params=(0, 2, 3))
def hlookup(lookup_value, table_array, row_index_num, range_lookup=True):
    """ Horizontal Lookup

    :param lookup_value: value to match (value or cell reference)
    :param table_array: range of cells being searched.
    :param row_index_num: column number to return
    :param range_lookup: True, assumes sorted, finds nearest. False: find exact
    :return: #N/A if not found else value
    """
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   hlookup-function-a3034eec-b719-4ba3-bb65-e1ad662ed95f

    if not list_like(table_array):
        return NA_ERROR

    if row_index_num <= 0:
        return VALUE_ERROR

    if row_index_num > len(table_array):
        return REF_ERROR

    result_idx = _match(
        lookup_value, table_array[0], match_type=bool(range_lookup))

    if isinstance(result_idx, int):
        return table_array[row_index_num - 1][result_idx - 1]
    else:
        # error string
        return result_idx


# def hyperlink(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   hyperlink-function-333c7ce6-c5ae-4164-9c47-7de9b76f577f


@excel_helper(err_str_params=(1, 2), number_params=(1, 2))
def index(array, row_num, col_num=None):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   index-function-a5dcf0dd-996d-40a4-a822-b56b061328bd

    if not list_like(array):
        if array in ERROR_CODES:
            return array
        else:
            return VALUE_ERROR
    if not list_like(array[0]):
        return VALUE_ERROR

    if is_address(array[0][0]):
        assert len({a for a in flatten(array)}) == 1
        _C_ = index.excel_func_meta['name_space']['_C_']
        ref_addr = array[0][0].address_at_offset
    else:
        ref_addr = None

    def array_data(row, col):
        if ref_addr:
            return _C_(ref_addr(row, col).address)
        else:
            return array[row][col]

    try:
        # rectangular array
        if row_num and col_num:
            if row_num < 0 or col_num < 0:
                return VALUE_ERROR
            else:
                return array_data(row_num - 1, col_num - 1)

        elif row_num:
            if row_num < 0:
                return VALUE_ERROR
            elif len(array[0]) == 1:
                return array_data(row_num - 1, 0)
            elif len(array) == 1:
                return array_data(0, row_num - 1)
            elif isinstance(array, np.ndarray):
                return array[row_num - 1, :]
            else:
                return (tuple(array_data(row_num - 1, col) for col in range(len(array[0]))),)

        elif col_num:
            if col_num < 0:
                return VALUE_ERROR
            elif len(array) == 1:
                return array_data(0, col_num - 1)
            elif len(array[0]) == 1:
                return array_data(col_num - 1, 0)
            elif isinstance(array, np.ndarray):
                result = array[:, col_num - 1]
                result.shape = result.shape + (1,)
                return result
            else:
                return tuple((array_data(row, col_num - 1), ) for row in range(len(array)))

    except IndexError:
        return REF_ERROR

    else:
        return array


@excel_helper(cse_params=0, number_params=1)
def indirect(ref_text, a1=True, sheet=''):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   indirect-function-474b3a3a-8a26-4f44-b491-92b6306fa261
    try:
        address = AddressRange.create(ref_text)
    except ValueError:
        return REF_ERROR
    if address.row > MAX_ROW or address.col_idx > MAX_COL:
        return REF_ERROR
    if not address.has_sheet:
        address = AddressRange.create(address, sheet=sheet)
    return address


@excel_helper(cse_params=0, err_str_params=0)
def lookup(lookup_value, lookup_array, result_range=None):
    """
    There are two ways to use LOOKUP: Vector form and Array form

    Vector form: lookup_array is list like (ie: n x 1)

    Array form: lookup_array is rectangular (ie: n x m)

        First row or column is the lookup vector.
        Last row or column is the result vector
        The longer dimension is the search dimension

    :param lookup_value: value to match (value or cell reference)
    :param lookup_array: range of cells being searched.
    :param result_range: (optional vector form) values are returned from here
    :return: #N/A if not found else value
    """
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   lookup-function-446d94af-663b-451d-8251-369d5e3864cb
    if not list_like(lookup_array):
        return NA_ERROR

    height = len(lookup_array)
    width = len(lookup_array[0])

    # match across the largest dimension
    if width <= height:
        match_idx = _match(lookup_value, tuple(i[0] for i in lookup_array))
        result = tuple(i[-1] for i in lookup_array)
    else:
        match_idx = _match(lookup_value, lookup_array[0])
        result = lookup_array[-1]

    if result_range is not None:
        # if not a vector return NA
        if not list_like(result_range):
            return NA_ERROR
        rr_height = len(result_range)
        rr_width = len(result_range[0])

        if rr_width < rr_height:
            if rr_width != 1:
                return NA_ERROR
            result = tuple(i[0] for i in result_range)
        else:
            if rr_height != 1:
                return NA_ERROR
            result = result_range[0]

    if isinstance(match_idx, int):
        return result[match_idx - 1]

    else:
        # error string
        return match_idx


@excel_helper(cse_params=0, number_params=2, err_str_params=(0, 2))
def match(lookup_value, lookup_array, match_type=1):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   match-function-e8dffd45-c762-47d6-bf89-533f4a37673a
    if len(lookup_array) == 1:
        lookup_array = lookup_array[0]
    else:
        lookup_array = tuple(row[0] for row in lookup_array)

    return _match(lookup_value, lookup_array, match_type)


@excel_helper(cse_params=(1, 2, 3, 4), ref_params=0, number_params=(1, 2))
def offset(reference, row_inc, col_inc, height=None, width=None):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   offset-function-c8de19ae-dd79-4b9b-a14e-b4d906d11b66
    """
    Returns a reference to a range that is a specified number of rows and
    columns from a cell or range of cells.
    """
    base_addr = AddressRange.create(reference)

    if height is None:
        height = base_addr.size.height
    if width is None:
        width = base_addr.size.width

    new_row = base_addr.row + row_inc
    end_row = new_row + height - 1
    new_col = base_addr.col_idx + col_inc
    end_col = new_col + width - 1

    if new_row <= 0 or end_row > MAX_ROW or new_col <= 0 or end_col > MAX_COL:
        return REF_ERROR

    top_left = AddressCell((new_col, new_row, new_col, new_row),
                           sheet=base_addr.sheet)
    if height == width == 1:
        return top_left
    else:
        bottom_right = AddressCell((end_col, end_row, end_col, end_row),
                                   sheet=base_addr.sheet)

        return AddressRange(f'{top_left.coordinate}:{bottom_right.coordinate}',
                            sheet=top_left.sheet)


@excel_helper(ref_params=0)
def row(ref):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   row-function-3a63b74a-c4d0-4093-b49a-e76eb49a6d8d
    if ref.is_range:
        if ref.end.row == 0:
            return range(1, MAX_ROW + 1)
        else:
            return tuple((c, ) for c in range(ref.start.row, ref.end.row + 1))
    else:
        return ref.row


# def rows(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   rows-function-b592593e-3fc2-47f2-bec1-bda493811597


# def rtd(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   rtd-function-e0cc001a-56f0-470a-9b19-9455dc0eb593


# def single(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   single-function-7ca229ca-13ae-420b-928e-2ef52a3805ff


# def sort(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   sort-function-22f63bd0-ccc8-492f-953d-c20e8e44b86c


# def sortby(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   sortby-function-cd2d7a62-1b93-435c-b561-d6a35134f28f


# def transpose(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   transpose-function-ed039415-ed8a-4a81-93e9-4b6dfac76027


# def unique(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   unique-function-c5ab87fd-30a3-4ce9-9d1a-40204fb85e1e


@excel_helper(cse_params=0, bool_params=3, number_params=2, err_str_params=(0, 2, 3))
def vlookup(lookup_value, table_array, col_index_num, range_lookup=True):
    """ Vertical Lookup

    :param lookup_value: value to match (value or cell reference)
    :param table_array: range of cells being searched.
    :param col_index_num: column number to return
    :param range_lookup: True, assumes sorted, finds nearest. False: find exact
    :return: #N/A if not found else value
    """
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   VLOOKUP-function-0BBC8083-26FE-4963-8AB8-93A18AD188A1

    if not list_like(table_array):
        return NA_ERROR

    if col_index_num <= 0:
        return '#VALUE!'

    if col_index_num > len(table_array[0]):
        return REF_ERROR

    result_idx = _match(
        lookup_value,
        [row[0] for row in table_array],
        match_type=bool(range_lookup)
    )

    if isinstance(result_idx, int):
        return table_array[result_idx - 1][col_index_num - 1]
    else:
        # error string
        return result_idx


@excel_helper()
def XLOOKUP(lookup_value, lookup_array, return_array, if_not_found="#N/A"):
    """
    Custom XLOOKUP implementation to replace unsupported pycel XLOOKUP function.
    
    Args:
        lookup_value: Value to search for
        lookup_array: Array/range to search in
        return_array: Array/range to return value from
        if_not_found: Value to return if not found (default "#N/A")
    
    Returns:
        Corresponding value from return_array or if_not_found
    """
    try:
        # Handle tuple of tuples (range format from pycel)
        if isinstance(lookup_array, tuple) and len(lookup_array) > 0:
            # Flatten the lookup array
            lookup_list = []
            for row in lookup_array:
                if isinstance(row, tuple):
                    lookup_list.extend(row)
                else:
                    lookup_list.append(row)
        else:
            lookup_list = lookup_array
            
        if isinstance(return_array, tuple) and len(return_array) > 0:
            # Flatten the return array
            return_list = []
            for row in return_array:
                if isinstance(row, tuple):
                    return_list.extend(row)
                else:
                    return_list.append(row)
        else:
            return_list = return_array
        
        # Find the lookup value
        for i, val in enumerate(lookup_list):
            if val == lookup_value:
                if i < len(return_list):
                    return return_list[i]
                else:
                    return if_not_found
        
        return if_not_found
        
    except Exception as e:
        return if_not_found


@excel_helper()
def _XLWS_FILTER(array, criteria1, criteria2=None, if_empty=""):
    """
    Custom _XLWS_FILTER implementation to replace unsupported pycel FILTER function.
    
    Args:
        array: Array to filter
        criteria1: Filter criteria (boolean array) - 1=include, 0=exclude
        criteria2: Second filter criteria (optional)
        if_empty: Value to return if no matches
    
    Returns:
        Filtered array or if_empty value
    """
    try:
        # Handle tuple of tuples (range format from pycel)
        if isinstance(array, tuple) and len(array) > 0:
            # Flatten the array
            array_list = []
            for row in array:
                if isinstance(row, tuple):
                    array_list.extend(row)
                else:
                    array_list.append(row)
        else:
            array_list = list(array) if hasattr(array, '__iter__') else [array]
        
        # Handle criteria (boolean arrays)
        if isinstance(criteria1, tuple) and len(criteria1) > 0:
            criteria1_list = []
            for row in criteria1:
                if isinstance(row, tuple):
                    criteria1_list.extend(row)
                else:
                    criteria1_list.append(row)
        else:
            criteria1_list = list(criteria1) if hasattr(criteria1, '__iter__') else [criteria1]
        
        if criteria2 is not None:
            if isinstance(criteria2, tuple) and len(criteria2) > 0:
                criteria2_list = []
                for row in criteria2:
                    if isinstance(row, tuple):
                        criteria2_list.extend(row)
                    else:
                        criteria2_list.append(row)
            else:
                criteria2_list = list(criteria2) if hasattr(criteria2, '__iter__') else [criteria2]
        else:
            criteria2_list = None
        
        # Apply filters
        filtered_results = []
        for i, value in enumerate(array_list):
            # Convert criteria to boolean (1 = True, 0 = False)
            if i < len(criteria1_list):
                criteria1_match = (criteria1_list[i] != 0)  # CRITICAL FIX: 1=True, 0=False
            else:
                criteria1_match = False
                
            if criteria2_list is not None:
                if i < len(criteria2_list):
                    criteria2_match = (criteria2_list[i] != 0)
                else:
                    criteria2_match = False
                criteria_match = criteria1_match and criteria2_match
            else:
                criteria_match = criteria1_match
                
            if criteria_match:
                # Skip header row - only include actual data
                if i > 0:  # Skip header at index 0
                    filtered_results.append(value)
        
        return filtered_results if filtered_results else if_empty
        
    except Exception as e:
        return if_empty


# def xmatch(value):
    # Excel reference: https://support.microsoft.com/en-us/office/
    #   xmatch-function-d966da31-7a6b-4a13-a1c6-5a33ed6a0312

__all__ = [
    'choose', 'column', 'hlookup', 'index', 'indirect', 'lookup', 'match',
    'offset', 'row', 'vlookup', 'XLOOKUP', '_XLWS_FILTER'
]