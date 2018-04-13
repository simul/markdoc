from pyparsing import *
from functools import *

#preparsed element, either text or command with parameters.
class ParsedElement(object):
	def __init__(self,kwd='',params=[],txt=''):
		self.text=txt
		self.keyword=kwd
		self.parameters=params

# This will contain the output of pyparsing.
class ParsedComment(object):
	def __init__(self):
		self.properties={}
		self.components=[]
	def clear(self):
		self.properties={}
		self.components=[]


class Parser:
	components=[]

	# Parse a command with variable arguments: insert it into the parsed comment
	def parseCommand(cmt, cnt, loc, toks):
		params=toks[2:cnt+1]
		txt=''.join(toks)
		el=ParsedElement(toks[1],params,txt)
		cmt.components.append(el)
		return toks
		
	def parseRef(cmt, strg, loc, toks):
		ref=toks[2]
		refname=toks[2]
		if len(toks)>3:
			refname=toks[3]
		el=(lineno(loc, strg),'','ref',ref,refname)
		cmt.components.append(el)
		return toks

	def parseDocumentProperty( cmt, cnt, loc, toks ):
		cmt.properties[toks[1]]=toks[2:]
		return ParsedElement(toks[1],toks[2:],''.join(toks))

	def parsePlainText( cmt, strg, loc, toks ):
		return toks

	def parseTest( cmt, cnt, strg, loc, toks ):
		return toks

	def parsePre( cmt, cnt, strg, loc, toks ):
		return toks

	def parsePost( cmt, cnt, strg, loc, toks ):
		return toks

	def parseBodyElement( cmt, cnt, strg, loc, toks ):
		return toks
		
	cmt=ParsedComment()
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

	#preparams = ZeroOrMore(param.setResultsName('preparam', listAllMatches=True)).setParseAction(partial(parsePost,cmt,1))
	postparams = ZeroOrMore(param.setResultsName('postparam', listAllMatches=True))
	preparams = ZeroOrMore(param.setResultsName('preparam', listAllMatches=True)).setParseAction(partial(parsePre,cmt,1))
	
	simpleline = NotAny('@') + (lineEnd | (Regex('[^\n]+') + lineEnd))
	simple = ZeroOrMore(simpleline).setResultsName('body') #.setParseAction(partial(parseTest,cmt,1)) #.setResultsName('parsedBody')
	#body = Combine(simple).setResultsName('body')


	space=White()
	backslash=oneOf('\\')
	title_k=backslash+Keyword('title')
	namespaces=(backslash+Keyword('namespaces')).setParseAction(partial(parseCommand,cmt,0))
	ref=(backslash+Keyword('ref')+identifier+Optional(identifier|quoted_identifier)).setParseAction(partial(parseRef,cmt))
	title=(title_k+space+(identifier|quoted_identifier)).setParseAction(partial(parseDocumentProperty,cmt,1))
	plainText=Regex('[^\n\\\\]+').setParseAction(partial(parsePlainText,cmt))
	command=(title|namespaces|ref)
	bodyElement=(command|plainText).setParseAction(partial(parseBodyElement,cmt,1))

	bodyLine = ( NotAny('@') + Group(ZeroOrMore(bodyElement)) + lineEnd).setParseAction(partial(parseTest,cmt,1))
	brief=(((backslash+Keyword('brief')).suppress()+simpleline)|(simpleline+lineEnd.suppress())).setResultsName('brief') #setParseAction(partial(parseDocumentProperty,cmt,1))
	parsedBody=Group(ZeroOrMore(bodyLine))
	
	doc = brief + preparams + simple + postparams
	part= parsedBody

	# Convert the ParseResults object into a components list.
	def parseResultsToComponents(self,parseResults):
		components=[]
		for res in parseResults:
			if not isinstance(res,str) and not isinstance(res,ParsedElement):
				components.extend(self.parseResultsToComponents(res))
			elif isinstance(res,ParsedElement):
				line_offset=0
				txt=res.text
				command=res.keyword
				ref=''.join(res.parameters)
				refname=''
				components.append((line_offset,txt,command,ref, refname))
			else:
				line_offset=0
				txt=res
				command=''
				ref=''
				refname=''
				components.append((line_offset,txt,command,ref, refname))
		return components

	# This method is intended to do the full parsing and cross-referencing.
	def parseFull(self,s):
		Parser.cmt=ParsedComment()
		u='''\\brief A microsecond timer.
		 Provides timing to microsecond accuracy; results are reported in milliseconds.'''
		ret=Parser.part.parseString(s)
		print(ret.dump())
		comp=self.parseResultsToComponents(ret)
		return comp
		#return Parser.cmt.components

	# This is the basic method that just splits the document into brief and doc.
	@staticmethod
	def parse(s):
		Parser.cmt=ParsedComment()
		ret=Parser.doc.parseString(s)
		print(ret.dump())
		ret.cmt=Parser.cmt
		#ret.brief=''
		return ret;