import sys, os
SIMUL=os.environ['SIMUL']
sys.path.append(SIMUL+'/External/cldoc')

os.environ["CLDOC_DEV"] = "1"
# import folder cldoc as a package.
import cldoc
print('SIMUL '+SIMUL)
VCINSTALLDIR='C:/Program Files (x86)/Microsoft Visual Studio 14.0/VC'
args=['generate','-I'+SIMUL,'-I'+SIMUL+'/..','-I"'+VCINSTALLDIR+'/atlmfc/include"','-I"'+VCINSTALLDIR+'/include"','-I"C:/Program Files (x86)/Windows Kits/10/Include/10.0.10240.0/ucrt"','-I"C:/Program Files/LLVM/bin/../lib/clang/6.0.0/include"','-std=c++1y','-fms-extensions','-fms-compatibility','-fms-compatibility-version=19','-Wno-deprecated-declarations','-Wno-ignored-attributes','-Wno-microsoft-template','-D_MSC_VER=1900','-DDOXYGEN=1','-Wno-pragma-once-outside-header','-Wno-unused-command-line-argument','--','--type=md','--loglevel=info','--output','C:/Simul/docs','--strip',SIMUL+'/','--md_output','ref']

source_dirs=['Base','Clouds','Sky','Math','Platform/CrossPlatform','PlugIns/TrueSkyPluginRender']
for d in  source_dirs:
	dir=SIMUL+'/'+d+'/*.h'
	args.append(dir)
args.extend(['--merge',SIMUL+'/Help/*.md','--clean','C:/Simul/docs/ref'])

args.extend(['--post',SIMUL+'/Help/build.bat'])

cldoc.run_generate(args)