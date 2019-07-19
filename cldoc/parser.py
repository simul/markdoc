from pyparsing import *
from functools import *
import re
import os
from . import utf8

#preparsed element, either text or command with parameters.
class ParsedElement(object):
	def __init__(self,node=None,ref=''):
		self.node=node
		self.refname=ref

class ParsedImage(object):
	def __init__(self, url, src, text=''):
		self.url=url
		self.title=text
		self.source_path=src

class ParsedReturn(object):
	def __init__(self,txt):
		self.text=txt

# A reference to a path not in the current build, but which may already exist on the target.
class ParsedReference(object):
	def __init__(self, url, src, text=''):
		self.url=url
		if text=='':
			text=url
		self.title=text
		self.source_path=src
		
class ParsedGitCmd(object):
	def __init__(self, src,toks=[]):
		self.source_path=src
		self.tokens=toks

# This will contain the output of pyparsing.
class ParsedComment(object):
	def __init__(self):
		self.properties={}
		self.components=[]
	def clear(self):
		self.properties={}
		self.components=[]

class Parser:
	# Parse a command with variable arguments: insert it into the parsed comment
	def parseCommand(self, cnt, loc, toks):
		params=toks[1:cnt+1]
		txt=''.join(toks)
		el=txt
		return utf8.utf8(txt)

	# link e.g. \link simul::sky::SkyKeyframer SkyKeyframer\endlink
	def parseLink(self,strg, loc, toks):
		return self.parseRef(strg,loc,toks)

	def message(self,type,loc,txt):
		ln=self.start_line+lineno(loc, self.src)
		print(self.filePath+'/'+self.src_file+'('+str(ln)+'): '+type+': '+txt)

	def error(self,loc,txt):
		self.message('Error',loc,txt)

	def warning(self,loc,txt):
		self.message('Warning',loc,txt)

	def parseRef(self, strg, loc, toks):
		ref=toks[0]
		refname=None
		if len(toks)>1:
			refname=toks[1]
		if self.resolver==None:
			return 'UnresolvedReference '+ref
		if isinstance(ref, utf8.string):
			names = ref.split('::')
		else:
			names = [ref]
		nds = [self.root]
		for j in range(len(names)):
			newnds = []
			for n in nds:
				newnds += self.resolver(n, names[j], j == 0)
			if len(newnds) == 0:
				break
			nds = newnds
		if len(newnds) > 0:
			return(ParsedElement(newnds, refname))
		# not found. Perhaps it's a classname under ref:
		nds = [self.root]
		names=['ref']+names
		for j in range(len(names)):
			newnds = []
			for n in nds:
				newnds += self.resolver(n, names[j], j == 0)
			if len(newnds) == 0:
				break
			nds = newnds
		if len(newnds) > 0:
			return(ParsedElement(newnds, refname))
		url='/'+('/'.join(names)).lower()
		self.warning(loc,'Unresolved reference '+ref+', assuming '+url)
		return ParsedReference(url,self.filePath,ref)

	def parseParam(self,toks):
		return utf8.utf8('\n**'+toks[0]+'**')

	def recurseNamespaces(self,node,level,limit):
		ret=[]
		if not node.has_any_docs():
			return ret
		refname=node.name
		tabs='	'*level+'- '
		ret.append(tabs)
		ret.append(ParsedElement([node], node.name))
		ret.append('\n')
		if level+1<limit:
			# sub-namespaces.
			child_nodes = []
			# match any child of this namespace
			child_nodes += self.resolver(node,re.compile('.*'), False, 'namespace')
			for child in child_nodes:
				c=self.recurseNamespaces(child,level+1,limit)
				if c:
					ret.extend(c)
		return ret

	def parseNamespaces(self,toks):
		if self.resolver==None:
			return 'Unresolved reference '
		depth=int(1)
		if len(toks)>1:
			depth=int(toks[1])
		nds = []
		# match any root namespace
		nds += self.resolver(self.root,re.compile('.*'), False, 'namespace')
		str=''

		ret=ParseResults()
		for n in nds:
			if n.has_any_docs():
				ret.extend(self.recurseNamespaces(n,0,depth))

		return ret

	def parseDocumentProperty( self, cnt, loc, toks ):
		self.properties[toks[0]]=toks[1]
		return utf8.utf8('') #ParsedElement(toks[0],toks[1:],''.join(toks))

	def parseEm(self, cnt, loc, toks ):
		# TODO: emphasis
		return utf8.utf8(toks[0])

	def parseReturn(self,cnt,loc,toks):
		return ParsedReturn(toks[0])

	def parseUnknownCommand(self,cnt,loc,toks):
		com=''
		if(len(toks)>0):
			com=toks[0]
		self.error(loc,'Unknown command '+com)
		return utf8.utf8('') #ParsedElement(toks[0],toks[1:],''.join(toks))

	def parseImage(self, cnt, loc, toks):
		title=''
		if(len(toks)>1):
			title=toks[1]
		return ParsedImage(toks[0],self.filePath,title)

	def parseGit(self, cnt, loc, toks):
		return ParsedGitCmd(self.filePath,toks)

	def parsePlainText( self, strg, loc, toks ):
		txt=''.join(toks)
		return utf8.utf8(txt)

	def parseTest( self, cnt, strg, loc, toks ):
		return toks

	def parsePre( self, cnt, strg, loc, toks ):
		return toks

	def parsePost( self, cnt, strg, loc, toks ):
		return toks

	def reset(self):
		self.properties={}

	def __init__(self):
		self.reset()
		self.resolver=None
		self.root=None
		self.filePath=None
		self.src=None
		self.src_file=None
		self.start_line=0
		ParserElement.setDefaultWhitespaceChars(' 	\r')
		
		#All variables defined on the class level in Python are considered static.
		# Here, we define static members of the class Parser, from pyparsing:
		identifier = Word(alphas + '_', alphanums + '_')
		qualified_identifier=Combine(identifier+ZeroOrMore('::'+identifier))
		quoted_identifier=QuotedString('"', escChar='\\')
		pt=Regex('[^\n\\\\]+')
		
		# I have modified the parser to make brief the default return, and body is optional. Only if there is a double lineEnd will there be a body,
		# and it is everything from the first such double lineEnd to the end of the text.
		#briefline = NotAny('@') + ((Regex('[^\n]+') + lineEnd))
		#brief = ZeroOrMore(lineEnd) + Combine(Optional(briefline)).setResultsName('brief') 
		
		paramdesc = restOfLine + ZeroOrMore(lineEnd + ~('@' | lineEnd) + Regex('[^\n]+')) + lineEnd.suppress()
		param = '@' + identifier.setResultsName('name') + White() + Combine(paramdesc).setResultsName('description')
		
		postparams = ZeroOrMore(param.setResultsName('postparam', listAllMatches=True))
		preparams = ZeroOrMore(param.setResultsName('preparam', listAllMatches=True)).setParseAction(partial(self.parsePre,1))
		
		simpleline = NotAny('@') + (lineEnd | (Regex('[^\n]+') + lineEnd))
		simple = Combine(ZeroOrMore(simpleline)).setResultsName('body')

		integer = Word(nums)
		space=White()
		backslash=oneOf('\\').suppress()
		namespaces=(backslash+Keyword('namespaces')+Optional(integer)).setParseAction(partial(self.parseNamespaces))
		ref=((backslash+Keyword('ref')).suppress()+space.suppress()+qualified_identifier).setParseAction(partial(self.parseRef))

		subpage=((backslash+Keyword('subpage')).suppress()+space.suppress()+qualified_identifier).setParseAction(partial(self.parseRef))

		ids=Combine(pt)
		link=((backslash+Keyword('link')).suppress()+space.suppress()+(qualified_identifier)+Optional(ids)+(backslash+Keyword('endlink'))).setParseAction(partial(self.parseLink))

		title_k=backslash+Keyword('title')
		title=(title_k+space.suppress()+(identifier|quoted_identifier)).setParseAction(partial(self.parseDocumentProperty,1))

		slug_k=backslash+Keyword('name')
		slug=(slug_k+space.suppress()+(qualified_identifier|quoted_identifier)).setParseAction(partial(self.parseDocumentProperty,1))

		em=((backslash+Keyword('em')+space).suppress()+(identifier|quoted_identifier)).setParseAction(partial(self.parseEm,1))
		a=((backslash+Keyword('a')+space).suppress()+(identifier|quoted_identifier)).setParseAction(partial(self.parseEm,1))
		param=((backslash+Keyword('param')+space).suppress()+(identifier|quoted_identifier)).setParseAction(partial(self.parseEm,1))
		
		_return=((backslash+Keyword('return')+space).suppress()+(ids)).setParseAction(partial(self.parseReturn,1))

		weight_k=backslash+Keyword('weight')
		weight=(weight_k+space.suppress()+integer).setParseAction(partial(self.parseDocumentProperty,1))

		layout_k=backslash+Keyword('layout')
		layout=(layout_k+space.suppress()+(identifier|quoted_identifier)).setParseAction(partial(self.parseDocumentProperty,1))

		image_k=backslash+Keyword('image')
		image=(image_k.suppress()+space.suppress()+Keyword('html').suppress()+space.suppress()+(identifier|quoted_identifier)).setParseAction(partial(self.parseImage,1))
		
		git_k=backslash+Keyword('git')
		git=(git_k.suppress()+space.suppress()+(identifier|quoted_identifier)+Optional(space.suppress()+identifier|quoted_identifier|integer)).setParseAction(partial(self.parseGit,1))
		
		unknown_k=backslash+identifier
		unknown_command=(unknown_k).setParseAction(partial(self.parseUnknownCommand,1))

		plainText=pt.setParseAction(partial(self.parsePlainText))
		command=(title|namespaces|ref|subpage|link|slug|em|a|param|_return|weight|layout|image|git|unknown_command)
		bodyElement=(command|plainText)
		
		bodyLine = ( NotAny('@') + Group(ZeroOrMore(bodyElement)) + lineEnd).setParseAction(partial(self.parseTest,1))
		brief=(Optional(Combine(((backslash+Keyword('brief')).suppress()+simpleline)|(simpleline+lineEnd.suppress()))).setResultsName('brief'))
		parsedBody=Group(ZeroOrMore(bodyLine))
		
		self.doc = brief + preparams + simple + postparams
		self.part= parsedBody

	# Convert the ParseResults object into a components list.
	# Basically we traverse the nodes and turn a tree into a list of the leaves.
	def parseResultsToComponents(self,parseResults):
		components=[]
		if isinstance(parseResults,ParsedElement):
			components.append((parseResults.node,parseResults.refname))
		#elif isinstance(parseResults,ParsedImage):
		#	components.append(parseResults)
		#elif isinstance(parseResults,ParsedGitCmd):
		#	components.append(parseResults)
		elif isinstance(parseResults,str) or not hasattr(parseResults, '__iter__'):
			components.append(parseResults)
		else:
			for res in parseResults:
				components.extend(self.parseResultsToComponents(res))
		return components

	# This method is intended to do the full parsing and cross-referencing.
	def parseFull(self,s,resolver,root,path,src_file,start_line):
		self.reset()
		self.resolver=resolver
		self.root=root
		self.filePath=path
		self.src=s
		self.src_file=src_file
		self.start_line=start_line
		ret=self.part.parseString(s)
		
		comp=self.parseResultsToComponents(ret)
		return comp

	# This is the basic method that just splits the document into brief and doc.
	
	def parse(self,s):
		self.reset()
		ret=self.doc.parseString(s)
		#print(ret.dump())
		return ret;