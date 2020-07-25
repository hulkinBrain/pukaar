from django import template

register = template.Library()

@register.filter
def range1(var, noOfPages):
    return range(noOfPages)

@register.filter
def index(indexable, i):
    return indexable[i]

@register.filter
def isEqual(getPage, forloopCounter):
    if getPage == str(forloopCounter):
        return True

@register.filter
def escapenewline(value):
    """
    Adds a slash before any newline. Useful for loading a multi-line html chunk
    into a Javascript variable.
    """
    value = value.replace('\n', '\\\n')
    return value
