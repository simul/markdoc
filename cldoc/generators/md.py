# This file is part of cldoc.  cldoc is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
from __future__ import absolute_import
from cldoc.clang import cindex

from .generator import Generator
from cldoc import nodes
from cldoc import example
from cldoc import utf8

from xml.etree import ElementTree
import sys, os

from cldoc import fs

class Md(Generator):
	def __init__(self, tree=None, opts=None):
		self.tree = tree
		self.options = opts
		self.namespaces_as_directories=True
		self._refid=None

	def generate(self, outdir):
		if not outdir:
			outdir = ''

		try:
			fs.fs.makedirs(outdir)
		except OSError:
			pass

		ElementTree.register_namespace('gobject', 'http://jessevdk.github.com/cldoc/gobject/1.0')
		ElementTree.register_namespace('cldoc', 'http://jessevdk.github.com/cldoc/1.0')

		self.index = ElementTree.Element('index')
		self.written = {}

		self.indexmap = {
			self.tree.root: self.index
		}

		cm = self.tree.root.comment

		if cm:
			if cm.brief:
				self.index.append(self.doc_to_md(self.tree.root, cm.brief, 'brief'))

			if cm.doc:
				self.index.append(self.doc_to_md(self.tree.root, cm.doc))

		Generator.generate(self, outdir)

		if self.options.report:
			self.add_report()

		#self.write_md(self.index, 'index.md')

		print('Generated `{0}\''.format(outdir))


	def add_report(self):
		from .report import Report

		reportname = 'report'

		while reportname + '.md' in self.written:
			reportname = '_' + reportname

		page = Report(self.tree, self.options).generate(reportname)

		elem = ElementTree.Element('report')
		elem.set('name', 'Documentation generator')
		elem.set('ref', reportname)

		self.index.append(elem)

		self.write_md(page, reportname + '.md')

	def indent(self, elem, level=0):
		i = "\n" + "  " * level

		if elem.tag == 'doc':
			return

		if len(elem):
			if not elem.text or not elem.text.strip():
				elem.text = i + "  "

			for e in elem:
				self.indent(e, level + 1)

				if not e.tail or not e.tail.strip():
					e.tail = i + "  "
			if not e.tail or not e.tail.strip():
				e.tail = i
		else:
			if level and (not elem.tail or not elem.tail.strip()):
				elem.tail = i

	def ref_to_link(self,rf):
		parts=rf.split('#')
		if len(parts)==2:
			link=parts[1]
			link=link.replace('::',self.namespace_separator)
			fullpath=os.path.join(self.outdir, link)
			# Now this link might contain a path, or the current page might have a path.
			relpath=os.path.relpath(fullpath,self.current_path).replace('\\','/')
			link=relpath
		else:
			link=''
		return link

	def link_md(self,title, rf):
		lnk=self.ref_to_link(rf)
		return '['+title+']('+lnk+')'

	def list_bases(self,f,elem):
		for child in elem.getchildren():
			self.indent(child)
			if child.tag=='type':
				title=child.attrib['name']
				ref=''
				if 'ref' in child.attrib:
					ref=child.attrib['ref']
				f.write(self.link_md(title,ref))
		f.write('\n')

	def get_return_type(self,elem):
		ret_parts=[]
		for child in elem.getchildren():
			if child.tag=='return':
				for c in child.getchildren():
					if c.tag=='type':
						ret_parts.append(c.attrib['name'])
						if 'qualifier' in c.attrib:
							ret_parts.append(c.attrib['qualifier']);
		ret_type=' '.join(ret_parts);
		return ret_type

	def get_brief(self,elem):
		brief=''
		for child in elem.getchildren():
			if child.tag=='brief':
				brief=child.text
		# can't have newlines without breaking the table structure.
		brief=brief.replace('\n','<br>')
		return brief
	
	def get_location(self,elem):
		location=''
		if 'location' in elem.attrib:
			return elem.attrib['location']
		return location
	def get_lib(self,elem):
		lib=''
		if 'lib' in elem.attrib:
			return elem.attrib['lib']
		return lib

	def get_doc(self,elem):
		doc=''
		for child in elem.getchildren():
			if child.tag=='doc':
				doc=self.process_elem(child)
		return doc

	def return_type(self,elem):
		ret_type=dict()
		for child in elem.getchildren():
			if child.tag=='type':
				ret_type['type']=child.attrib['name']
		return ret_type
				
	def argument(self,elem):
		ret_arg=dict()
		ret_arg['name']=elem.attrib['name']
		for child in elem.getchildren():
			if child.tag=='type':
				if 'name' in child.attrib:
					ret_arg['type']=child.attrib['name']
				else:
					ret_arg['type']=''
		return ret_arg

	def get_arguments(self,elem):
		arguments=[]
		for child in elem.getchildren():
			if child.tag=='argument':
				arguments.append(self.argument(child))
		return arguments

	def get_arguments_text(self,elem):
		arguments=self.get_arguments(elem)
		args_txt=[]
		for arg in arguments:
			args_txt.append(arg['name'])
		arglist=','.join(args_txt)
		return arglist

	def get_typed_arguments_text(self,elem):
		arguments=self.get_arguments(elem)
		args_txt=[]
		for arg in arguments:
			tp_parts=[]
			if arg['type']!='':
				tp_parts.append(arg['type'])
			if arg['name']!='':
				tp_parts.append(arg['name'])
			tp=' '.join(tp_parts)
			args_txt.append(tp)
		arglist=', '.join(args_txt)
		return arglist
	
	def has_doc(self,elem):
		for child in elem.getchildren():
			if child.tag=='brief' or child.tag=='doc':
				if child.text!='':
					return True
			if self.has_doc(child):
				return True
		return False

	def doc_method(self,f,elem):
		ret_type=''
		doc=''
		brief=''
		for child in elem.getchildren():
			if child.tag=='return':
				ret_type=self.get_return_type(elem)
			elif child.tag=='brief':
				brief=child.text
			elif child.tag=='doc':
				doc=child.text
		#blank line before a heading h4:
		f.write('\n### <a name="'+elem.attrib['name']+'"/>'+ret_type+' '+elem.attrib['name'])

		arglist=self.get_typed_arguments_text(elem)
		f.write('('+arglist+')')
		f.write('\n')
		if brief!='':
			f.write(brief+'\n')
		if doc!='':
			f.write(doc+'\n')
	def get_docs(self,elem):
		doc=''
		brief=''
		for child in elem.getchildren():
			if child.tag=='brief':
				brief=child.text
			elif child.tag=='doc':
				doc=child.text
		return brief,doc

	def doc_typedef(self,f,elem):
		brief,doc=self.get_docs(elem)
		if brief!='' or doc!='':
			f.write('\n**'+elem.attrib['name']+'** '+brief+' '+doc+'\n')

	def doc_enum(self,f,elem):
		brief,doc=self.get_docs(elem)
		if brief!='' or doc!='':
			f.write('\n**'+elem.attrib['name']+'** '+brief+' '+doc+'\n')

	def doc_field(self,f,elem):
		brief,doc=self.get_docs(elem)
		if brief!='' or doc!='':
			f.write('\n**'+elem.attrib['name']+'** '+brief+' '+doc+'\n')

	def process_text(self,txt):
		return txt

	def process_elem(self,elem):
		res=elem.text
		for child in elem.getchildren():
			if child.tag=="ref":
				title=child.text
				if 'ref' in child.attrib:
					link=self.ref_to_link(child.attrib['ref'])
					#res+='[{0}]({1})'.format(title,link)
					res+='<a href="{1}">{0}</a>'.format(title,link)
				res+=child.tail
			else:
				res+=self.process_elem(child)
		res+=elem.tail
		return res

	def write_md(self, elem, fname):

		self.written[fname] = True
		fullpath=os.path.join(self.outdir, fname)

		tree = ElementTree.ElementTree(elem)

		self.indent(tree.getroot())
		if 'title' in elem.attrib:
			title=elem.attrib['title']
		elif 'name' in elem.attrib:
			title=elem.attrib['name']
		elif elem.tag=='index':
			title='Index'
		else:
			title='Untitled'

		weight=0
		if 'weight' in elem.attrib:
			weight=elem.attrib['weight']
		layout_name='reference'

		# if(elem.tag=='category'):
		#else:
		#	fullpath=os.path.join(os.path.join(self.outdir, 'ref'),fname)

		self.current_path=''
		try:
			head_tail=os.path.split(fullpath)
			self.current_path=head_tail[0]
			os.makedirs(self.current_path)
		except:
			pass
		location=self.get_location(elem)
		print(location+' (0): Documenting '+title)

		f = fs.fs.open(fullpath, 'w')
		f.write('---\n'+'title: '+title+'\nlayout: '+layout_name+'\nweight: '+str(weight)+'\n---\n')
		brief=self.get_brief(elem)
		doc=self.get_doc(elem)
		if(elem.tag=='category'):
			f.write(title)
			f.write('\n===\n\n')
			f.write(brief)
			f.write(doc)
		else:
			if elem.tag=='index' or elem.tag=='root':
				f.write(title)
			else:
				f.write(elem.tag+' '+title)
			f.write('\n===\n\n')
			lib=self.get_lib(elem)
			if location and location!='':
				f.write('| Include: | '+location+' |\n\n')
			if lib and lib!='':
				f.write('| Library: | '+lib+' |\n\n')

			if brief=='':
				brief=doc
			if doc=='':
				doc=brief
			if brief:
				f.write(brief+'\n')

			# method declarations
			f.write('\n')
			namespaces=[]
			classes=[]
			methods=[]
			bases=[]
			fields=[]
			typedefs=[]
			enums=[]
			variables=[]
			for child in elem.getchildren():
				if child.tag=='base':
					bases.append(child)
				elif child.tag=='class' or child.tag=='struct':
					if self.has_doc(child):
						classes.append(child)
				elif child.tag=='method' or child.tag=='function' or child.tag=='constructor' or child.tag=='destructor':
					if self.has_doc(child):
						methods.append(child)
				elif child.tag=='namespace':
					if self.has_doc(child):
						namespaces.append(child)
				elif child.tag=='field':
					if self.has_doc(child):
						fields.append(child)
				elif child.tag=='typedef':
					if self.has_doc(child):
						typedefs.append(child)
				elif child.tag=='enum':
					if self.has_doc(child):
						enums.append(child)
				elif child.tag=='variable':
					if self.has_doc(child):
						variables.append(child)
				elif child.tag=='brief' or child.tag=='doc':
					pass
				else:
					print(child.tag)
			
			for child in namespaces:
				title=child.tag+' '+child.attrib['name']
				ref=child.attrib['ref']
				lnk=self.ref_to_link(ref)
				#f.write(self.link_md(title,ref)+'\n')
				br=self.get_brief(child).replace('\n','')
				f.write('\n| ['+title+']('+lnk+') | '+br+' |')
			
			# children:
			if len(bases):	
				for child in bases:
					self.indent(child)
					self.list_bases(f,child)

			if len(classes):	
				f.write('\nClasses and Structures\n---\n')  
				for child in classes:
					title=child.attrib['name']
					ref=child.attrib['ref']
					if self.has_doc(child):
						lnk=self.ref_to_link(ref)
						title='['+title+']('+lnk+')'
					else:
						continue
					br=self.get_brief(child)
					f.write('\n| '+child.tag+' '+title+' | '+br+' |')
				f.write('\n')
				
			if len(methods):	
				f.write('\nFunctions\n---\n')  
				for child in methods:
					f.write('\n| '+self.get_return_type(child)+' | ['+child.attrib['name']+'](#'+child.attrib['name']+')('+self.get_typed_arguments_text(child)+') |')
					any_methods=True

			f.write('\n')
			# main text
			if doc:
				f.write('\n'+doc+'\n')
			f.write('\n')

			if len(bases)>0:
				f.write('\nBase Classes\n---\n')
				for child in bases:
					self.indent(child)
					if child.tag=='base':
						self.list_bases(f,child)

			if len(methods)>0:
				f.write('\nFunctions\n---\n')
				for child in methods:
					self.indent(child)
					self.doc_method(f,child)
			
			if len(fields)>0:
				f.write('\nFields\n---\n')	 
			if len(variables)>0:
				f.write('\nVariables\n---\n')	
			if len(typedefs)>0:
				f.write('\nTypedefs\n---\n')	
				for child in typedefs:
					self.indent(child)
					self.doc_typedef(f,child)
			if len(enums)>0:
				f.write('\nEnums\n---\n')   
				for child in enums:
					self.indent(child)
					self.doc_enum(f,child)	

			for child in fields:
				self.indent(child)
				self.doc_field(f,child)
			#tree.write(f, encoding='utf-8', xml_declaration=True)

		f.close()

	def is_page(self, node):
		if node.force_page:
			return True

		if isinstance(node, nodes.Struct) and node.is_anonymous:
			return False

		if isinstance(node, nodes.Class):
			for child in node.children:
				if not (isinstance(child, nodes.Field) or \
						isinstance(child, nodes.Variable) or \
						isinstance(child, nodes.TemplateTypeParameter)):
					return True

			return False

		pagecls = [nodes.Namespace, nodes.Category, nodes.Root]

		for cls in pagecls:
			if isinstance(node, cls):
				return True

		if isinstance(node, nodes.Typedef) and len(node.children) > 0:
			return True

		return False

	def is_top(self, node):
		if self.is_page(node):
			return True

		if node.parent == self.tree.root:
			return True

		return False

	def refid(self, node):
		try:
			if not node._refid is None:
				return node._refid
		except:
			return ''

		parent = node

		meid = node.qid

		if not node.parent or (isinstance(node.parent, nodes.Root) and not self.is_page(node)):
			return 'index#' + meid

		# Find topmost parent
		while not self.is_page(parent):
			parent = parent.parent

		if not node is None:
			node._refid = parent.qid + '#' + meid
			return node._refid
		else:
			return None

	def add_ref_node_id(self, node, elem):
		r = self.refid(node)

		if not r is None:
			elem.set('ref', r)

	def add_ref_id(self, cursor, elem):
		if not cursor:
			return

		if cursor in self.tree.cursor_to_node:
			node = self.tree.cursor_to_node[cursor]
		elif cursor.get_usr() in self.tree.usr_to_node:
			node = self.tree.usr_to_node[cursor.get_usr()]
		else:
			return

		self.add_ref_node_id(node, elem)

	def type_to_md(self, tp, parent=None):
		elem = ElementTree.Element('type')

		if tp.is_constant_array:
			elem.set('size', str(tp.constant_array_size))
			elem.set('class', 'array')
			elem.append(self.type_to_md(tp.element_type, parent))
		elif tp.is_function:
			elem.set('class', 'function')

			result = ElementTree.Element('result')
			result.append(self.type_to_md(tp.function_result, parent))
			elem.append(result)

			args = ElementTree.Element('arguments')
			elem.append(args)

			for arg in tp.function_arguments:
				args.append(self.type_to_md(arg, parent))
		else:
			elem.set('name', tp.typename_for(parent))

		if len(tp.qualifier) > 0:
			elem.set('qualifier', tp.qualifier_string)

		if tp.builtin:
			elem.set('builtin', 'yes')

		if tp.is_out:
			elem.set('out', 'yes')

		if tp.transfer_ownership != 'none':
			elem.set('transfer-ownership', tp.transfer_ownership)

		if tp.allow_none:
			elem.set('allow-none', 'yes')

		self.add_ref_id(tp.decl, elem)
		return elem

	def enumvalue_to_md(self, node, elem):
		elem.set('value', str(node.value))

	def enum_to_md(self, node, elem):
		if not node.typedef is None:
			elem.set('typedef', 'yes')

		if node.isclass:
			elem.set('class', 'yes')

	def struct_to_md(self, node, elem):
		self.class_to_md(node, elem)

		if not node.typedef is None:
			elem.set('typedef', 'yes')

	def templatetypeparameter_to_md(self, node, elem):
		dt = node.default_type

		if not dt is None:
			d = ElementTree.Element('default')

			d.append(self.type_to_md(dt))
			elem.append(d)

	def templatenontypeparameter_to_md(self, node, elem):
		elem.append(self.type_to_md(node.type))

	def function_to_md(self, node, elem):
		if not (isinstance(node, nodes.Constructor) or
				isinstance(node, nodes.Destructor)):
			ret = ElementTree.Element('return')

			if not node.comment is None and hasattr(node.comment, 'returns') and node.comment.returns:
				ret.append(self.doc_to_md(node, node.comment.returns))

			tp = self.type_to_md(node.return_type, node.parent)

			ret.append(tp)
			elem.append(ret)

		for arg in node.arguments:
			ret = ElementTree.Element('argument')
			ret.set('name', arg.name)
			ret.set('id', arg.qid)

			if not node.comment is None and arg.name in node.comment.params:
				ret.append(self.doc_to_md(node, node.comment.params[arg.name]))

			ret.append(self.type_to_md(arg.type, node.parent))
			elem.append(ret)

	def method_to_md(self, node, elem):
		self.function_to_md(node, elem)

		if len(node.override) > 0:
			elem.set('override', 'yes')

		for ov in node.override:
			ovelem = ElementTree.Element('override')

			ovelem.set('name', ov.qid_to(node.qid))
			self.add_ref_node_id(ov, ovelem)

			elem.append(ovelem)

		if node.virtual:
			elem.set('virtual', 'yes')

		if node.static:
			elem.set('static', 'yes')

		if node.abstract:
			elem.set('abstract', 'yes')

	def typedef_to_md(self, node, elem):
		elem.append(self.type_to_md(node.type, node))

	def typedef_to_md_ref(self, node, elem):
		elem.append(self.type_to_md(node.type, node))

	def variable_to_md(self, node, elem):
		elem.append(self.type_to_md(node.type, node.parent))

	def property_to_md(self, node, elem):
		elem.append(self.type_to_md(node.type, node.parent))

	def set_access_attribute(self, node, elem):
		if node.access == cindex.AccessSpecifier.PROTECTED:
			elem.set('access', 'protected')
		elif node.access == cindex.AccessSpecifier.PRIVATE:
			elem.set('access', 'private')
		elif node.access == cindex.AccessSpecifier.PUBLIC:
			elem.set('access', 'public')

	def process_bases(self, node, elem, bases, tagname):
		for base in bases:
			child = ElementTree.Element(tagname)

			self.set_access_attribute(base, child)

			child.append(self.type_to_md(base.type, node))

			if base.node and not base.node.comment is None and base.node.comment.brief:
				child.append(self.doc_to_md(base.node, base.node.comment.brief, 'brief'))

			elem.append(child)

	def process_subclasses(self, node, elem, subclasses, tagname):
		for subcls in subclasses:
			child = ElementTree.Element(tagname)

			self.set_access_attribute(subcls, child)
			self.add_ref_node_id(subcls, child)

			child.set('name', subcls.qid_to(node.qid))

			if not subcls.comment is None and subcls.comment.brief:
				child.append(self.doc_to_md(subcls, subcls.comment.brief, 'brief'))

			elem.append(child)

	def class_to_md(self, node, elem):
		self.process_bases(node, elem, node.bases, 'base')
		self.process_bases(node, elem, node.implements, 'implements')

		self.process_subclasses(node, elem, node.subclasses, 'subclass')
		self.process_subclasses(node, elem, node.implemented_by, 'implementedby')

		hasabstract = False
		allabstract = True

		for method in node.methods:
			if method.abstract:
				hasabstract = True
			else:
				allabstract = False

		if hasabstract:
			if allabstract:
				elem.set('interface', 'true')
			else:
				elem.set('abstract', 'true')

	def field_to_md(self, node, elem):
		elem.append(self.type_to_md(node.type, node.parent))

	def doc_to_md(self, parent, doc, tagname='doc'):
		doce = ElementTree.Element(tagname)

		s = ''
		last = None

		for component in doc.components:
			if isinstance(component, utf8.string):
				s += component
			elif isinstance(component, example.Example):
				# Make highlighting
				if last is None:
					doce.text = s
				else:
					last.tail = s

				s = ''

				code = ElementTree.Element('code')
				doce.append(code)

				last = code

				for item in component:
					if item.classes is None:
						s += item.text
					else:
						last.tail = s

						s = ''
						par = code

						for cls in item.classes:
							e = ElementTree.Element(cls)

							par.append(e)
							par = e

						par.text = item.text
						last = par

				if last == code:
					last.text = s
				else:
					last.tail = s

				s = ''
				last = code
			elif len(component)==2 and isinstance(component[0][0],nodes.Node):
				if last is None:
					doce.text = s
				else:
					last.tail = s

				s = ''

				nds = component[0]
				refname = component[1]

				# Make multiple refs
				for ci in range(len(nds)):
					cc = nds[ci]

					last = ElementTree.Element('ref')

					if refname:
						last.text = refname
					elif cc.title:
						last.text=cc.title
					else:
						last.text = parent.qlbl_from(cc)

					self.add_ref_node_id(cc, last)

					if ci != len(nds) - 1:
						if ci == len(nds) - 2:
							last.tail = ' and '
						else:
							last.tail = ', '

					doce.append(last)
			else:
				pass

		if last is None:
			doce.text = s
		else:
			last.tail = s

		return doce

	def call_type_specific(self, node, elem, fn):
		clss = [node.__class__]

		while len(clss) > 0:
			cls = clss[0]
			clss = clss[1:]

			if cls == nodes.Node:
				continue

			nm = cls.__name__.lower() + '_' + fn

			if hasattr(self, nm):
				getattr(self, nm)(node, elem)
				break

			if cls != nodes.Node:
				clss.extend(cls.__bases__)

	def node_to_md(self, node):
		elem = ElementTree.Element(node.classname)
		props = node.props

		for prop in props:
			if props[prop]:
				elem.set(prop, props[prop])
		if node.cursor:
			location=node.cursor.location.file.name
			if location!='':
				location=location.replace('\\','/')
				location=location.replace('//','/')
				if self.options.strip!=None:
					location=location.replace(self.options.strip,'')
				elem.set('location',location)
		if not node.comment is None and node.comment.brief:
			elem.append(self.doc_to_md(node, node.comment.brief, 'brief'))

		if not node.comment is None and node.comment.doc:
			elem.append(self.doc_to_md(node, node.comment.doc))

		self.call_type_specific(node, elem, 'to_md')

		for child in node.sorted_children():
			if child.access == cindex.AccessSpecifier.PRIVATE:
				continue

			self.refid(child)

			if self.is_page(child):
				chelem = self.node_to_md_ref(child)
			else:
				chelem = self.node_to_md(child)

			elem.append(chelem)

		return elem

	def templated_to_md_ref(self, node, element):
		for child in node.sorted_children():
			if not (isinstance(child, nodes.TemplateTypeParameter) or isinstance(child, nodes.TemplateNonTypeParameter)):
				continue

			element.append(self.node_to_md(child))

	def generate_page(self, node):
		# ignore nodes containing no documentation
		if not node.has_any_docs():
			return
		elem = self.node_to_md(node)
		self.namespace_separator='.'
		if self.namespaces_as_directories==True:
			self.namespace_separator='/'
		self.write_md(elem, node.output_filename(self.namespace_separator) + '.md')

	def node_to_md_ref(self, node):
		elem = ElementTree.Element(node.classname)
		props = node.props

		# Add reference item to index
		self.add_ref_node_id(node, elem)
		
		if 'title' in props:
			elem.set('title', props['title'])
		if 'name' in props:
			elem.set('name', props['name'])
		if 'weight' in props:
			elem.set('weight', props['weight'])

		# can't put arbitrary text into brief, because markdown is replaced with html.
		# if not node.comment is None and node.comment.brief:
		#	elem.append(self.doc_to_md(node, node.comment.brief, 'brief'))

		self.call_type_specific(node, elem, 'to_md_ref')

		return elem

	def generate_node(self, node):
		# Ignore private stuff
		if node.access == cindex.AccessSpecifier.PRIVATE:
			return

		self.refid(node)

		if self.is_page(node):
			elem = self.node_to_md_ref(node)
			if node.parent:
				self.indexmap[node.parent].append(elem)
			self.indexmap[node] = elem

			self.generate_page(node)
		elif self.is_top(node):
			self.index.append(self.node_to_md(node))

		if isinstance(node, nodes.Namespace) or isinstance(node, nodes.Category):
			# Go deep for namespaces and categories
			Generator.generate_node(self, node)
		elif isinstance(node, nodes.Class):
			# Go deep, but only for inner classes
			Generator.generate_node(self, node, lambda x: isinstance(x, nodes.Class))

# vi:ts=4:et
