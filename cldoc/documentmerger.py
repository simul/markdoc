import os, subprocess

import comment
import nodes
import sys, re

from . import fs

class DocumentMerger:
    reinclude = re.compile('#<cldoc:include[(]([^)]*)[)]>')
    reheading = re.compile('(.*)\\s*{#(?:([0-9]*):)?(.*)}')
    def merge(self, mfilter, files):
        for f in files:
            if os.path.basename(f).startswith('.'):
                continue

            if os.path.isdir(f):
                self.merge(mfilter, [os.path.join(f, x) for x in os.listdir(f)])
            elif f.endswith('.md'):
                self._merge_file(mfilter, f)

    def _split_categories(self, filename, contents):
        lines = contents.splitlines()

        ret = {}
        title={}
        category = None
        doc = []
        first = False
        ordered = []
        weight = {}
        this_weight=0

        for line in lines:
            prefix = '#<cldoc:'

            line = line.rstrip('\n')

            if first:
                first = False

                if line == '':
                    continue
            heading=DocumentMerger.reheading.search(line)
            if line.startswith(prefix) and line.endswith('>'):
                if len(doc) > 0 and not category:
                    sys.stderr.write('Failed to merge file `{0}\': no #<cldoc:id> specified\n'.format(filename))
                    sys.exit(1)

                if category:
                    if not category in ret:
                        ordered.append(category)

                    ret[category] = "\n".join(doc)

                doc = []
                category = line[len(prefix):-1]
                this_title=category.strip()
                first = True
            elif heading:
                if heading.group(2):
                    this_weight=int(heading.group(2))
                category=heading.group(3)
                this_title=heading.group(1).strip()
            else:
                doc.append(line)
        if not this_weight:
            this_weight=0
        if not category and len(doc) > 0:
            parts=filename.replace('\\','/').replace('.md','').split('/')
            category=parts[len(parts)-1]
            this_title=category

        if category:
            if not category in ret:
                ordered.append(category)
            title[category]=this_title
            ret[category] = "\n".join(doc)
            weight[category] = this_weight

        return [[c, ret[c],title[c],weight[c]] for c in ordered]

    def _normalized_qid(self, qid):
        #if qid == 'index':
        #    return None

        if qid.startswith('::'):
            return qid[2:]

        return qid

    def _do_include(self, mfilter, filename, relpath):
        if not os.path.isabs(relpath):
            relpath = os.path.join(os.path.dirname(filename), relpath)

        return self._read_merge_file(mfilter, relpath)

    def _process_includes(self, mfilter, filename, contents):
        def repl(m):
            return self._do_include(mfilter, filename, m.group(1))

        return DocumentMerger.reinclude.sub(repl, contents)

    def _read_merge_file(self, mfilter, filename):
        if not mfilter is None:
            contents = unicode(subprocess.check_output([mfilter, filename]), 'utf-8')
        else:
            contents = unicode(fs.fs.open(filename).read(), 'utf-8')

        return self._process_includes(mfilter, filename, contents)

    def _merge_file(self, mfilter, filename):
        contents = self._read_merge_file(mfilter, filename)
        categories = self._split_categories(filename, contents)

        for (category, docstr, cat_title, weight) in categories:
            # First, split off any order number from the front e.g. 3:name
            category=category.replace('::','_DOUBLECOLONSEPARATOR_')
            front_back= category.split(':')
            front=''
            if len(front_back)>1:
                category=front_back[1]
                front=front_back[0]
            else:
                category=front_back[0]
            category=category.replace('_DOUBLECOLONSEPARATOR_','::')
            parts = category.split('/')

            qid = self._normalized_qid(parts[0])
            key = 'doc'

            #if len(parts) > 1:
            #    key = parts[1]

            if not self.qid_to_node[qid]:
                self.add_categories([[qid,cat_title]])
                node = self.category_to_node[qid]
            else:
                node = self.qid_to_node[qid]
            node.weight=weight
            if key == 'doc':
                node.merge_comment(comment.Comment(docstr, None, self.options), override=True)
            else:
                sys.stderr.write('Unknown type `{0}\' for id `{1}\'\n'.format(key, parts[0]))
                sys.exit(1)

    def add_categories(self, categories):
        root = None

        for category,title in categories:
            parts = category.split('::')

            root = self.root
            fullname = ''

            for i in range(len(parts)):
                part = parts[i]
                found = False

                if i != 0:
                    fullname += '::'

                fullname += part

                for child in root.children:
                    if isinstance(child, nodes.Category) and child.name == part:
                        root = child
                        found = True
                        break

                if not found:
                    s = nodes.Category(part,title)

                    root.append(s)
                    root = s

                    self.category_to_node[fullname] = s
                    self.qid_to_node[s.qid] = s
                    self.all_nodes.append(s)

        return root

# vi:ts=4:et
