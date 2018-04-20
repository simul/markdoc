from pyparsing import *
from functools import *
import re
from . import utf8

#preparsed element, either text or command with parameters.
class ParsedElement(object):
	def __init__(self,node=None,ref=''):
		self.node=node
		self.refname=ref

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
		
	def parseRef(self, strg, loc, toks):
		ref=toks[1]
		refname=toks[1]
		if len(toks)>2:
			refname=toks[2]
		if self.resolver==None:
			return 'UnresolvedReference '+ref
		#el=(lineno(loc, strg),'','ref',ref,refname)
		
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
			return (newnds, refname)
		return 'Unresolved reference '+ref

	def parseParam(self,toks):
		return utf8.utf8('\n**'+toks[0]+'**')

	def recurseNamespaces(self,node,level,limit):
		ret=[]
		if not node.has_any_docs():
			return ret
		refname=node.name
		tabs='\t'*level+'- '
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
		ParserElement.setDefaultWhitespaceChars(' \t\r')
		
		#All variables defined on the class level in Python are considered static.
		# Here, we define static members of the class Parser, from pyparsing:
		identifier = Word(alphas + '_', alphanums + '_')
		quoted_identifier=QuotedString('"', escChar='\\')
		
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
		title_k=backslash+Keyword('title')
		namespaces=(backslash+Keyword('namespaces')+Optional(integer)).setParseAction(partial(self.parseNamespaces))
		ref=(backslash+Keyword('ref')+identifier+Optional(identifier|quoted_identifier)).setParseAction(partial(self.parseRef))
		title=(title_k+space.suppress()+(identifier|quoted_identifier)).setParseAction(partial(self.parseDocumentProperty,1))
		plainText=Regex('[^\n\\\\]+').setParseAction(partial(self.parsePlainText))
		command=(title|namespaces|ref)
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
		elif isinstance(parseResults,str) or not hasattr(parseResults, '__iter__'):
			components.append(parseResults)
		else:
			for res in parseResults:
				components.extend(self.parseResultsToComponents(res))
		return components

	# This method is intended to do the full parsing and cross-referencing.
	def parseFull(self,s,resolver,root):
		self.reset()
		self.resolver=resolver
		self.root=root
		ret=self.part.parseString(s)
		#print(ret.dump())
		comp=self.parseResultsToComponents(ret)
		return comp

	# This is the basic method that just splits the document into brief and doc.
	
	def parse(self,s):
		self.reset()
		ret=self.doc.parseString(s)
		#print(ret.dump())
		return ret;