from django import template

register = template.Library()

@register.filter
def range1(var, noOfPages):
    return range(noOfPages)

@register.filter
def isEqual(getPage, forloopCounter):
    if getPage == str(forloopCounter):
        return True