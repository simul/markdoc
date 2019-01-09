import sys, os
SIMUL=os.environ['SIMUL']
SIMUL=SIMUL.replace('\\','/')
print('SIMUL dir '+SIMUL)
sys.path.append(SIMUL+'/External/cldoc')
os.environ["CLDOC_DEV"] = "1"
# import folder cldoc as a package.
import cldoc
print('SIMUL '+SIMUL)
VCINSTALLDIR='C:/Program Files (x86)/Microsoft Visual Studio 14.0/VC'

try:
	VULKAN_SDK=os.environ["VULKAN_SDK"]
except:
	pass
VULKAN_SDK='D:/Code/VulkanSDK'
VULKAN_SDK=VULKAN_SDK.replace('\\','/')
print('VULKAN_SDK '+VULKAN_SDK)
args=['generate'
	  ,'-I"C:/Program Files/LLVM/lib/clang/7.0.0/include"'
	  ,'-I'+SIMUL
	  ,'-I'+SIMUL+'/..','-I"'+VCINSTALLDIR+'/atlmfc/include"','-I"'+VCINSTALLDIR+'/include"'
	  ,'-I"C:/Program Files (x86)/Windows Kits/10/Include/10.0.17763.0/ucrt"'
	  ,'-I'+VULKAN_SDK+'/Include','-F'+VULKAN_SDK+'/Include'
	  ,'-std=c++1y'
	  ,'-fms-extensions'
	  ,'-fms-compatibility'
	  ,'-fms-compatibility-version=19'
	  ,'-Wno-deprecated-declarations'
	  ,'-Wno-ignored-attributes'
	  ,'-Wno-microsoft-template'
	  ,'-D_MSC_VER=1900'
	  ,'-DDOXYGEN=1'
	  ,'-MD'
	  ,'-MF foo.d'
	  ,'-Wno-pragma-once-outside-header'
	  ,'-Wno-unused-command-line-argument'
	  ,'--'
	  ,'--type=md'
	  ,'--loglevel=info'
	  ,'--output','C:/Simul/docs'
	  ,'--strip',SIMUL+'/'
	  ,'--md_output','ref'
	  ,'--image-path','C:/Simul/4.2/Simul/Help/Images']
os.environ['INCLUDE']=''
source_dirs=['PlugIns/TrueSkyPluginRender','Base','Math','Geometry','Sky','Clouds','Terrain','Platform/CrossPlatform']
for d in  source_dirs:
	dir=SIMUL+'/'+d+'/*.h'
	args.append(dir)
#args.append('C:/Temp/UnityPluginInterface.h')
args.extend(['--merge',SIMUL+'/Help/*.md']) #,'--clean','C:/Simul/docs/ref'

#args.extend(['--post',SIMUL+'/Help/build.bat'])
print(' '.join(args))
cldoc.run_generate(args)