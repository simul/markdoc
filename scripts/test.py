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
	VULKAN_SDK='D:/Code/VulkanSDK'
VULKAN_SDK=VULKAN_SDK.replace('\\','/')
print('VULKAN_SDK '+VULKAN_SDK)
args=['C:/Simul/4.2/Simul/Simul.markdoc']
os.environ['INCLUDE']=''
source_dirs=['Base']#,'Math','Geometry','Sky','Clouds','Terrain','Platform/CrossPlatform','Plugins/PluginRenderInterface']
for d in  source_dirs:
	dir=SIMUL+'/'+d+'/*.h'
	args.append(dir)
#args.append('C:/Temp/UnityPluginInterface.h')
args.extend(['--merge',SIMUL+'/Help/*.md'])
args.extend(['--merge',SIMUL+'/Help/**/*.md'])
args.extend(['--clean','C:/Simul/docs/ref'])

args.extend(['--post',SIMUL+'/Help/build.bat'])
print(' '.join(args))
cldoc.run_generate(args)