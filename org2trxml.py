#!/usr/bin/python
import sys
import lxml.etree as et
import argparse
import os
import subprocess
import re

def parse_org(args):
    XSD_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
    XSD = "{%s}" % XSD_NAMESPACE
    NSMAP = {"xsi" : XSD_NAMESPACE} # the default namespace (no prefix)

    testdef = et.Element("testdefinition", version="1.0", nsmap=NSMAP)
    testdef.set(XSD+"noNamespaceSchemaLocation", "/srv/mer/sdks/sdk/usr/share/test-definition/testdefinition-tm_terms.xsd")
    element_map=("set", "case", "step")

    comment = re.compile(r"\s*#(.*)$") # matches a comment - res.group 1=text
    bullet = re.compile(r"(\*+)\s*(.*?)(\s+(:[:\S]+:))?$") # matches bullets - res.group: 1=bullets 2=txt 3=tags
    text = re.compile(r"[^\*](.*)$") # matches non bullet lines (and comments) - res.group: 1=txt

    cur_el = testdef
    desc = None
    in_preamble = True
    cur_depth = 0
    with sys.stdin as org:

        for line in org:
            res = comment.match(line)
            if res:
                cur_el.append(et.Comment(res.group(1)))
                continue

            res = text.match(line)
            if res:
                if in_preamble:
                    raise Exception("Not allowed to have text prior to first bullet")
                line = line.strip()
                if desc is None:
                    desc = et.SubElement(cur_el, "description")
                    desc.text = line
                else:
                    desc.text += " " + line
                continue


            res = bullet.match(line)
            if not res:
                raise  Exception("Unexpected line: %s" % line)

            in_preamble = False
            depth = len(res.group(1))
            txt = res.group(2).strip()
            tags = res.group(4)
            if tags:
                tags = tags.split(":")[1:-1]
            else:
                tags = []    

            # This element has no <description> yet
            desc = None

            # Determine our parent element
            if depth == cur_depth + 1:
                parent = cur_el
            elif depth > cur_depth:
                raise  Exception("Can't skip a level")
            else:
                parent=cur_el.getparent()
                for i in range(cur_depth - depth):
                    parent = parent.getparent()
            cur_depth = depth

            if depth == 1:
                cur_el = et.SubElement(parent, "suite", name=txt)

            if depth == 2:
                cur_el = et.SubElement(parent, "set", name=txt)

            if depth == 3:
                cur_el = et.SubElement(parent, "case", name=txt)
                if not "AUTO" in tags:
                    cur_el.set("manual", "true")

            if depth == 4:
                cur_el = et.SubElement(parent, "step")
                cur_el.text = txt
                
    return testdef

def emit_xml(args,root):
    # Save XML
    sys.stdout.write(et.tostring(root, pretty_print=True))


def get_xml(args):
    # http://lxml.de/FAQ.html#why-doesn-t-the-pretty-print-option-reformat-my-xml-output
    parser = et.XMLParser(remove_blank_text=True)
    try:
        return et.parse(sys.stdin, parser).getroot()
    except :
        print "Error loading xml"
        sys.exit()

# recursive org emitter
def emit_org(args, element, org, context={'depth':0}):

    if not isinstance(element.tag, basestring):
        # assume it's a comment
        org.write("# %s\n" % element.text)
        return

    if element.tag == "testdefinition":
        pass
    elif element.tag == "suite":
        org.write("* %s\n" % element.get("name"))
        context['depth']=2
    elif element.tag == "set":
        org.write("** %s\n" % element.get("name"))
        context['depth']=3
    elif element.tag == "case":
        if element.get("manual") != "true":
            context['manual_case']=False
        else:
            context['manual_case']=True
        if context['manual_case']:
            org.write("*** %s\n" % element.get("name"))
        else:
            org.write("*** {:<50} :AUTO:\n".format(element.get("name")))
        context['depth']=4
    elif element.tag == "step":
        # Step is same as case unless manual is set
        tag=None
        if element.get("manual") is not None:
            if element.get("manual") == "true":
                if not context['manual_case']:
                    tag="MANUAL"
            else:
                if context['manual_case']:
                    tag="AUTO"
        if tag:
            org.write("**** {:<50} :{}:\n".format(element.text or "", tag))
        else:
            org.write("*** %s\n" % (element.text or ""))
        context['depth']=5
    elif element.tag == "description":
        org.write("%s%s\n" % (" "* context['depth'], (element.text or "")))
        context['depth']=4
    else:
        print "Unknown element %s" % element

    for el in element:
        emit_org(args, el, org, context)

parser = argparse.ArgumentParser(description='Writes xml from org mode')

parser.add_argument('--to-xml', action='store_true',
                    help="Convert org to xml")
parser.add_argument('--to-org', action='store_true',
                    help="Convert xml to org")

args = parser.parse_args()

if args.to_xml:
    root = parse_org(args)
    emit_xml(args, root)
elif args.to_org:
    root = get_xml(args)
    print root
    emit_org(args, root, sys.stdout)
else:
    print "Must use either --to-xml or --to-org"

