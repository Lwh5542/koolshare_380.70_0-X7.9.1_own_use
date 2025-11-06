# koolshare_380.70_0-X7.9.1_own_use

备忘录养老版梅林380

腾达Ac18刷的梅林固件380.70_0-X7.9.1

打开梅林的ssh

然后vi /koolshare/scripts/ks_app_install.sh

文件中搜索找到

wget --no-check-certificate --tries=1 --timeout=15 $TAR_URL

这一行，在前面加#注释掉，或者删除掉然后在下面加入以下内容：

LOGGER "Download URL: $TAR_URL"

curl -k -L -o "/tmp/$FNAME" "$TAR_URL"

因为官方固件的koolshare.ngrok.wang早已失联

所以软件中心0.0需要换源

sed -i 's/koolshare.ngrok.wang/自己服务器部署的域名/g' /koolshare/scripts/ks_app_install.sh

sed -i 's/koolshare.ngrok.wang/自己服务器部署的域名/g' /koolshare/webs/Main_Soft_center.asp
然后就会加载出1.4.8.0版本的软件中心，直接更新软件中心

更新完成后还需要在来一遍 因为又覆盖了之前的修改

vi /koolshare/scripts/ks_app_install.sh

文件搜索找到

wget --no-check-certificate --tries=1 --timeout=15 $TAR_URL

这一行，在前面加#注释掉，或者删除掉然后在下面加入以下内容：

LOGGER "Download URL: $TAR_URL"

curl -k -L -o "/tmp/$FNAME" "$TAR_URL"

因为更新的软件中心是别人编译好的所以内置域名是ks.ddnsto.com

这个域名时常发癫，所以替换为自己服务器部署

sed -i 's/ks.ddnsto.com/自己服务器部署的域名/g' /koolshare/scripts/ks_app_install.sh

sed -i 's/ks.ddnsto.com/自己服务器部署的域名/g' /koolshare/webs/Main_Soft_center.asp
然后就可以正常安装插件了

往后全靠我们自己的服务器维护 不走第三方维护

