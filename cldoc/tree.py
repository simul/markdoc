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
# -*- coding: utf-8 -*-

from .clang import cindex
import tempfile
import functools

from .defdict import Defdict

from . import comment
from . import nodes
from . import includepaths
from . import documentmerger

from . import example
from . import utf8
from . import log

# RVK: to enable multithreaded processing by clang.
import threading
import time

threadLock = threading.Lock()

class myThread (threading.Thread):
	def __init__(self, tree, threadID, filename, index,flags, options, files, comment):
		threading.Thread.__init__(self)
		self.tree=tree
		self.threadID = threadID
		self.filename = filename
		self.index=index
		self.flags = flags
		self.options=options
		self.headers = {}
		self.processed = {}
		#self.categories = Comment.RangeMap()
		self.commentsdbs = Defdict()
		self.tu=None
		self.includes={}
		self.extractfiles=[filename]
		self.files=files
		self.db=None
		self.comment=comment
	def run(self):
		#print ("Starting " + self.name)
		#print_time(self.name, self.counter, 3)
		print('{0} (0): '.format(self.filename))
		try:
			self.tu = self.index.parse(self.filename, self.flags, options=cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
			
			self.db=comment.CommentsDatabase(self.filename, self.tu, self.options)
			"""for inc in self.tu.get_includes():
				filename = str(inc.include)
				self.includes[filename] = True
				
			for filename in self.includes:
				if (not filename in self.files) or filename in self.extractfiles:
					continue

				self.extractfiles.append(filename)

			for e in self.extractfiles:
				if e in self.processed:
					continue
				self.db=comment.CommentsDatabase(e, self.tu, self.options)"""

		except cindex.LibclangError as e:
			sys.stderr.write("\nError: Failed to parse.\n" + str(e) + "\n\n")
			
		
		if len(self.tu.diagnostics) != 0:
			fatal = False

			for d in self.tu.diagnostics:
				#rewrite Clang errors in visual studio format.
				# e.g. C:\\vector.h:249:43: error: function declared 'cdecl' here was previously declared without calling convention
				# becomes C:\\vector.h(249): error: function declared 'cdecl' here was previously declared without calling convention
				# bizarrely, the disabling option doesn't work in Clang. So let's apply it here:
				if d.disable_option in self.flags:
					continue
				formatted=re.sub(":(\d+):(?:\d+):", "(\\1):", d.format())
				sys.stderr.write(formatted)
				sys.stderr.write("\n")

				if d.severity == cindex.Diagnostic.Fatal or \
				   d.severity == cindex.Diagnostic.Error:
					fatal = True

			if fatal:
				sys.stderr.write("\nCould not generate documentation due to parser errors\n")
				sys.exit(1)

			if not self.tu:
				sys.stderr.write("Could not parse file %s...\n" % (f,))
				sys.exit(1)
				
			#Get lock to synchronize threads
			threadLock.acquire()
			for filename in self.includes:
				self.tree.headers[filename] = True

			# Extract comments from files and included files that we are
			# supposed to inspect

			for e in self.extractfiles:
				if e in self.tree.processed:
					continue
				self.tree.add_categories(self.db.category_names)
				self.tree.commentsdbs[e] = self.db

			
			#self.tree.processing[self.filename]=True
			# Free lock to release next thread
			threadLock.release()
			self.tree.visit(self.tu.cursor.get_children())
			#threadLock.acquire()
			#self.tree.processed[self.filename]=True
			#self.tree.processing[self.filename]=False
			# Free lock to release next thread
			#threadLock.release()

from .cmp import cmp

import os, sys, re, glob, platform

from ctypes.util import find_library

if platform.system() == 'Darwin':
	libclangs = [
		'/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib',
		'/Library/Developer/CommandLineTools/usr/lib/libclang.dylib'
	]

	found = False

	for libclang in libclangs:
		if os.path.exists(libclang):
			cindex.Config.set_library_path(os.path.dirname(libclang))
			found = True
			break

	if not found:
		lname = find_library("clang")

		if not lname is None:
			cindex.Config.set_library_file(lname)
else:
	libclangs = [
		'C:/Program Files/LLVM/bin'
	]

	found = False

	for libclang in libclangs:
		fclang=libclang+'/libclang.dll'
		if os.path.exists(fclang):
			cindex.Config.set_library_path(os.path.dirname(fclang))
			os.environ['Path']=libclang+";"+os.environ['Path']
			found = True
			break
	if not found:
		versions = [None, '7.0', '6.0', '5.0', '4.0', '3.9', '3.8', '3.7', '3.6', '3.5', '3.4', '3.3', '3.2']

		for v in versions:
			name = 'clang'

			if not v is None:
				name += '-' + v

			lname = find_library(name)

			if not lname is None:
				cindex.Config.set_library_file(lname)
				break

testconf = cindex.Config()

try:
	testconf.get_cindex_library()
except cindex.LibclangError as e:
	sys.stderr.write("\nFatal: Failed to locate libclang library. cldoc depends on libclang for parsing sources, please make sure you have libclang installed.\n" + str(e) + "\n\n")
	sys.exit(1)

class Tree(documentmerger.DocumentMerger):
	def __init__(self, files, flags, options):
		self.processed = {}
		self.files, ok = self.expand_sources([os.path.realpath(f) for f in files])

		if not ok:
			sys.exit(1)

		self.flags = includepaths.flags(flags)

		# Sort files on sources, then headers
		self.files.sort(key=functools.cmp_to_key(lambda a, b: cmp(self.is_header(a), self.is_header(b))))

		#self.processing = {}
		self.kindmap = {}

		# Things to skip
		self.kindmap[cindex.CursorKind.USING_DIRECTIVE] = None

		# Create a map from CursorKind to classes representing those cursor
		# kinds.
		for cls in nodes.Node.subclasses():
			if hasattr(cls, 'kind'):
				self.kindmap[cls.kind] = cls

		self.root = nodes.Root()

		self.all_nodes = []
		self.cursor_to_node = Defdict()
		self.usr_to_node = Defdict()
		self.qid_to_node = Defdict()

		# Map from category name to the nodes.Category for that category
		self.category_to_node = Defdict()

		self.options=options
		# Map from filename to comment.CommentsDatabase
		self.commentsdbs = Defdict()

		self.qid_to_node[None] = self.root
		self.usr_to_node[None] = self.root

	def _lookup_node_from_cursor_despecialized(self, cursor):
		template = cursor.specialized_cursor_template

		if template is None:
			parent = self.lookup_node_from_cursor(cursor.semantic_parent)
		else:
			return self.lookup_node_from_cursor(template)

		if parent is None:
			return None

		for child in parent.children:
			if child.name == cursor.spelling:
				return child

		return None

	def lookup_node_from_cursor(self, cursor):
		if cursor is None:
			return None

		# Try lookup by direct cursor reference
		node = self.cursor_to_node[cursor]

		if not node is None:
			return node

		node = self.usr_to_node[cursor.get_usr()]

		if not node is None:
			return node

		return self._lookup_node_from_cursor_despecialized(cursor)

	def filter_source(self, path):
		return path.endswith('.c') or path.endswith('.cpp') or path.endswith('.h') or path.endswith('.cc') or path.endswith('.hh') or path.endswith('.hpp')

	def expand_sources(self, sources, filter=None):
		ret = []
		ok = True

		for source in sources:
			if not filter is None and not filter(source):
				continue

			if os.path.isdir(source):
				retdir, okdir = self.expand_sources([os.path.join(source, x) for x in os.listdir(source)], self.filter_source)

				if not okdir:
					ok = False

				ret += retdir
			elif not os.path.exists(source):
				sys.stderr.write("The specified source `" + source + "` could not be found\n")
				ok = False
			else:
				ret.append(source)

		return (ret, ok)

	def is_header(self, filename):
		return filename.endswith('.hh') or filename.endswith('.hpp') or filename.endswith('.h')

	def find_node_comment(self, node):

		for location in node.comment_locations:
			db = self.commentsdbs[location[0]]

			if db:
				cm = db.lookup(location)

				if cm:
					return cm

		return None

	def process(self):
		"""
		process processes all the files with clang and extracts all relevant
		nodes from the generated AST
		"""

		self.index = cindex.Index.create()
		self.headers = {}
		thread_id =1
		threads = []

		for f in self.files:
			if f in self.processed:
				continue
			
			# Create new threads
			thr = myThread(self, thread_id, f, self.index,self.flags,self.options, self.files, comment)
			thread_id=thread_id+1
			# Start new Threads
			thr.run()
			
			# Add threads to thread list
			threads.append(thr)
			
		# Wait for all threads to complete
		#for t in threads:
		#	t.join()
		#self.processing = {}

		# Construct hierarchy of nodes.
		for node in self.all_nodes:
			if node==None:
				continue
			q = node.qid

			if node.parent is None:
				par = self.find_parent(node)

				# Lookup categories for things in the root
				if (par is None or par == self.root) and (not node.cursor is None):
					location = node.cursor.extent.start
					db = self.commentsdbs[location.file.name]

					if db:
						par = self.category_to_node[db.lookup_category(location)]

				if par is None:
					par = self.root

				par.append(node)

			# Resolve comment
			cm = self.find_node_comment(node)

			if cm:
				node.merge_comment(cm)

		# Keep track of classes to resolve bases and subclasses
		classes = {}

		# Map final qid to node
		for node in self.all_nodes:
			q = node.qid
			self.qid_to_node[q] = node

			if isinstance(node, nodes.Class):
				classes[q] = node

		# Resolve bases and subclasses
		for qid in classes:
			classes[qid].resolve_bases(classes)

	def markup_code(self, index):
		for node in self.all_nodes:
			if node.comment is None:
				continue

			if not node.comment.doc:
				continue

			comps = node.comment.doc.components

			for i in range(len(comps)):
				component = comps[i]

				if not isinstance(component, comment.Comment.Example):
					continue

				text = str(component)

				tmpfile = tempfile.NamedTemporaryFile(mode='w',delete=False)
				tmpfile.write(text)
				filename = tmpfile.name
				tmpfile.close()

				tu = index.parse(filename, self.flags, options=1)
				tokens = tu.get_tokens(extent=tu.get_extent(filename, (0, os.stat(filename).st_size)))
				os.unlink(filename)

				hl = []
				incstart = None

				for token in tokens:
					start = token.extent.start.offset
					end = token.extent.end.offset

					if token.kind == cindex.TokenKind.KEYWORD:
						hl.append((start, end, 'keyword'))
						continue
					elif token.kind == cindex.TokenKind.COMMENT:
						hl.append((start, end, 'comment'))

					cursor = token.cursor

					if cursor.kind == cindex.CursorKind.PREPROCESSING_DIRECTIVE:
						hl.append((start, end, 'preprocessor'))
					elif cursor.kind == cindex.CursorKind.INCLUSION_DIRECTIVE and incstart is None:
						incstart = cursor
					elif (not incstart is None) and \
						 token.kind == cindex.TokenKind.PUNCTUATION and \
						 token.spelling == '>':
						hl.append((incstart.extent.start.offset, end, 'preprocessor'))
						incstart = None

				ex = example.Example()
				lastpos = 0

				for ih in range(len(hl)):
					h = hl[ih]

					ex.append(text[lastpos:h[0]])
					ex.append(text[h[0]:h[1]], h[2])

					lastpos = h[1]

				ex.append(text[lastpos:])
				comps[i] = ex

	def match_ref(self, child, name):
		if isinstance(name, utf8.string):
			return name == child.name
		else:
			return name.match(child.name)

	def find_ref(self, node, name, goup, kind=None):
		if node is None:
			return []

		ret = []

		for child in node.resolve_nodes:
			if kind!=None and (not hasattr(child, 'kind') or child.kind==None or child.kind.name.lower()!=kind.lower()):
				continue
			if self.match_ref(child, name):
				ret.append(child)

		if goup and len(ret) == 0:
			return self.find_ref(node.parent, name, True, kind)
		else:
			return ret

	def cross_ref_node(self, node):
		if not node.comment is None:
			node.comment.resolve_refs(self.find_ref, node)
			for key in node.comment.global_properties:
				val=node.comment.global_properties[key]
				if key=='title':
					node.set_title(val)
				elif key=='slug' or key=='name':
					node.slug=val
				elif key=='weight':
					node.weight=val
				elif key=='layout':
					node.layout=val

		for child in node.children:
			self.cross_ref_node(child)

	def cross_ref(self):
		self.cross_ref_node(self.root)
		self.markup_code(self.index)

	def decl_on_c_struct(self, node, tp):
		n = self.cursor_to_node[tp.decl]

		if isinstance(n, nodes.Struct) or \
		   isinstance(n, nodes.Typedef) or \
		   isinstance(n, nodes.Enum):
			return n

		return None

	def c_function_is_constructor(self, node):
		hints = ['new', 'init', 'alloc', 'create']

		for hint in hints:
			if node.name.startswith(hint + "_") or \
			   node.name.endswith("_" + hint):
				return True

		return False

	def node_on_c_struct(self, node):
		if isinstance(node, nodes.Method) or \
		   not isinstance(node, nodes.Function):
			return None

		decl = None

		if self.c_function_is_constructor(node):
			decl = self.decl_on_c_struct(node, node.return_type)

		if not decl:
			args = node.arguments

			if len(args) > 0:
				decl = self.decl_on_c_struct(node, args[0].type)

		return decl

	def find_parent(self, node):
		cursor = node.cursor

		# If node is a C function, then see if we should group it to a struct
		# RVK: Wait, what?
		parent = self.node_on_c_struct(node)

		if parent:
			return parent

		while cursor:
			cursor = cursor.semantic_parent
			parent = self.cursor_to_node[cursor]

			if parent:
				return parent

		return self.root

	def register_node(self, node, parent=None):
		self.all_nodes.append(node)

		self.usr_to_node[node.cursor.get_usr()] = node
		self.cursor_to_node[node.cursor] = node

		# Typedefs in clang are not parents of typedefs, but we like it better
		# that way, explicitly set the parent directly here
		if parent and isinstance(parent, nodes.Typedef):
			parent.append(node)

		if parent and hasattr(parent, 'current_access'):
			node.access = parent.current_access

	def register_anon_typedef(self, node, parent):
		node.typedef = parent
		node.add_comment_location(parent.cursor.extent.start)

		self.all_nodes.remove(parent)

		# Map references to the typedef directly to the node
		self.usr_to_node[parent.cursor.get_usr()] = node
		self.cursor_to_node[parent.cursor] = node

	def cursor_is_exposed(self, cursor):
		# Only cursors which are in headers are exposed.
		filename = str(cursor.location.file)
		return filename in self.headers or self.is_header(filename)

	def is_unique_anon_struct(self, node, parent):
		if not node:
			return False

		if not isinstance(node, nodes.Struct):
			return False

		if not (node.is_anonymous or not node.name):
			return False

		return not isinstance(parent, nodes.Typedef)

	def visit(self, citer, parent=None):
		"""
		visit iterates over the provided cursor iterator and creates nodes
		from the AST cursors.
		"""
		if not citer:
			return
		while True:
			try:
				item = next(citer)
			except StopIteration:
				return
		
			#if locstr in self.processing:
			#	continue

			# Ignore unexposed things
			if item.kind == cindex.CursorKind.UNEXPOSED_DECL:
				#self.visit(item.get_children(), parent)		And don't visit their children!
				continue
			
			if item.kind in self.kindmap:
				cls = self.kindmap[item.kind]

				if not cls:
					# Skip
					continue
				
				f = item.location.file
				# Check the source of item
				if not f:
					self.visit(item.get_children())
					continue
				locstr=str(f)
				# Ignore files other than the ones we are scanning for
				if not locstr in self.files:
					continue
				# Ignore files we already processed
				if locstr in self.processed:
					continue
				threadLock.acquire()
				ln=item.location.line
				#print(locstr+"("+str(ln)+"): visiting "+item.displayname)
				#self.processing[locstr] = True
				threadLock.release()
				# see if we already have a node for this thing
				# usr, or Unified Symbol Resolution (USR) is a string that identifies a
				# particular entity (function, class, variable, etc.)
				node = self.usr_to_node[item.get_usr()]

				if not node or self.is_unique_anon_struct(node, parent):
					# Only register new nodes if they are exposed.
					if self.cursor_is_exposed(item):
						node = cls(item, None)
						threadLock.acquire()
						self.register_node(node, parent)
						threadLock.release()

				elif isinstance(parent, nodes.Typedef) and isinstance(node, nodes.Struct):
					# Typedefs are handled a bit specially because what happens
					# is that clang first exposes an unnamed struct/enum, and
					# then exposes the typedef, with as a child again the
					# cursor to the already defined struct/enum. This is a
					# bit reversed as to how we normally process things.
					threadLock.acquire()
					self.register_anon_typedef(node, parent)
					threadLock.release()
				else:
					threadLock.acquire()
					self.cursor_to_node[item] = node
					node.add_ref(item)
					threadLock.release()

				if node and node.process_children:
					self.visit(item.get_children(), node)
				#threadLock.acquire()
				#self.processing[locstr] = False
				#threadLock.release()
			else:
				par = self.cursor_to_node[item.semantic_parent]

				if not par:
					par = parent

				if par:
					ret = par.visit(item, citer)

					if not ret is None:
						for node in ret:
							threadLock.acquire()
							self.register_node(node, par)
							threadLock.release()

				'''ignoretop = [cindex.CursorKind.FRIEND_DECL, cindex.CursorKind.TYPE_REF, cindex.CursorKind.TEMPLATE_REF, cindex.CursorKind.NAMESPACE_REF,cindex.CursorKind.PARM_DECL,cindex.CursorKind.MACRO_INSTANTIATION,cindex.CursorKind.INCLUSION_DIRECTIVE ,cindex.CursorKind.MACRO_DEFINITION,cindex.CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION]

				if (not par or ret is None) and not item.kind in ignoretop:
					log.warning("Unhandled cursor: %s", item.kind)'''
			

# vi:ts=4:et
