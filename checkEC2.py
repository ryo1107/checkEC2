import boto3
from tabulate import tabulate
# import numpy as np
import pprint
import sys
pp = pprint.PrettyPrinter(indent=4)

## AWSのprofile指定 and Client作成
session = boto3.Session(profile_name=sys.argv[1]) #場合によってはpython実行時引数(sys.argv)で指定する様にするかも？
if len(sys.argv)==4:
    ec2_resource = session.resource("ec2",region_name=sys.argv[3])
    cw_resource = session.resource("cloudwatch",region_name=sys.argv[3])

elif len(sys.argv)==3:
    ec2_resource = session.resource("ec2",region_name="ap-northeast-1")
    cw_resource = session.resource("cloudwatch",region_name="ap-northeast-1")

else:
    print("引数不足です。次のように実行してください。\nPlease input <$ python file.py profile_name InstanceId (resion_name)>")
    sys.exit()

ec2_client = ec2_resource.meta.client
cw_client = cw_resource.meta.client

## IAM付きlambda等
# ec2_client = boto3.client("ec2")
# cw_client = boto3.client("cloudwatch")

class pycolor:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    PURPLE = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    RETURN = '\033[07m' #反転
    ACCENT = '\033[01m' #強調
    FLASH = '\033[05m' #点滅
    RED_FLASH = '\033[05;41m ' #赤背景+点滅
    END = ' \033[0m'
# 使い方の例 print(pycolor.RED + "RED TEXT" + pycolor.END)

#instances_info=[{インスタンス1個目の情報},{2個目の情報}.....]
def get_instances_info(ec2_client,instanceId):
    instances_info = []
    #インスタンス情報をインスタンスごとに取得
    reservations = ec2_client.describe_instances()["Reservations"] 
    for reserv in reservations:
        # print(reserv)
        try: #IAMロールがふられていた場合
            instances_info.append({
                "InstanceId":reserv["Instances"][0]["InstanceId"],
                "ImageId":reserv["Instances"][0]["ImageId"],
                "InstanceType":reserv["Instances"][0]["InstanceType"],
                "SecurityGroupId":reserv["Instances"][0]["SecurityGroups"][0]["GroupId"],
                "AvailabilityZone":reserv["Instances"][0]["Placement"]["AvailabilityZone"],
                "IAM":reserv["Instances"][0]["IamInstanceProfile"]["Arn"].split("/")[-1] #IAMがなければここでエラーが出て例外処理へ
            })
        except: #IAMロールがふられていなかった場合
            instances_info.append({
                "InstanceId":reserv["Instances"][0]["InstanceId"],
                "ImageId":reserv["Instances"][0]["ImageId"],
                "InstanceType":reserv["Instances"][0]["InstanceType"],
                "SecurityGroupId":reserv["Instances"][0]["SecurityGroups"][0]["GroupId"],
                "AvailabilityZone":reserv["Instances"][0]["Placement"]["AvailabilityZone"],
                "IAM":"-"
            })
        if reserv["Instances"][0]["InstanceId"] == instanceId:
            return instances_info[-1]

#EC2インスタンスがアラーム設定を持っているか否か
def get_cloudwatch_alarms(cw_client,instanceId):
    responceS = cw_client.describe_alarms()["MetricAlarms"]
    for responce in responceS:
        if responce["Dimensions"][0]["Value"]==instanceId:
            return "OK"
        else:
            pass
    return pycolor.RED_FLASH+"None"+pycolor.END

#EBSでどの種類の記録媒体を使っているかと、そのサイズ
def get_vol_size_type(ec2_client,instance_info):
    vol_res = ec2_client.describe_volumes(Filters=[{'Name': 'attachment.instance-id','Values': [instance_info["InstanceId"],]},])
    vol_size,vol_type = vol_res["Volumes"][0]["Size"],vol_res["Volumes"][0]["VolumeType"]
    if vol_type=="gp2":
        vol_type="汎用SSD"
        vol_type=pycolor.RED_FLASH+vol_type+pycolor.END
    elif vol_type=="io1":
        vol_type="プロビジョンドIOPS SSD"
        vol_type=pycolor.RED_FLASH+vol_type+pycolor.END
    elif vol_type=="sc1":
        vol_type="コールドHDD"
        vol_type=pycolor.RED_FLASH+vol_type+pycolor.END
    elif vol_type=="standard":
        vol_type="マグネティック"
    else:
        vol_type="error"
        vol_type=pycolor.RED_FLASH+vol_type+pycolor.END
    # print(str(vol_size)+"GB:"+vol_type)
    return vol_size,vol_type

#削除保護が有効か否か
def get_del_protect(ec2_client,instance_info):
    del_protect = ec2_client.describe_instance_attribute(Attribute="disableApiTermination",InstanceId=instance_info["InstanceId"])["DisableApiTermination"]["Value"]

    if del_protect:
        del_protect="Enable"
    else:
        del_protect=pycolor.RED_FLASH+"disable"+pycolor.END
    return del_protect

#EIPがあるか否か
def get_eip_info(ec2_client,instance_info):
    EIP = ec2_client.describe_addresses(Filters=[{'Name': 'instance-id','Values': [instance_info["InstanceId"],]},])["Addresses"] != []
    if EIP:
        EIP="OK"
    else:
        EIP=pycolor.RED_FLASH+"None"+pycolor.END
    return EIP

#CPUバーストが有効か否か
def get_cpu_burst(ec2_client,instance_info):
    cpu_burst = ec2_client.describe_instance_credit_specifications(InstanceIds=[instance_info["InstanceId"]])["InstanceCreditSpecifications"][0]["CpuCredits"]
    if cpu_burst=="standard":
        return "OK-Disable"
    else:
        return pycolor.RED_FLASH+"NG-Enable"+pycolor.END

#IAMロールがEC2_COMMONであるか否か
def check_IAM(instance_info):
    if instance_info["IAM"]=="EC2_COMMON":
        return "OK"
    else:
        return pycolor.RED_FLASH+"NG"+pycolor.END

#セキュリティーポートが25,80,443以外全開放出ないか判定
def get_security_port(ec2_client,instance_info):
    responceS = ec2_client.describe_security_groups(GroupIds=[instance_info["SecurityGroupId"]])["SecurityGroups"][0]["IpPermissions"]
    # pp.pprint(responceS)
    security_check_result=[]
    for responce in responceS:
        #全開放のポート取得
        try:
            ip_bool = responce["IpRanges"][0]["CidrIp"]=="0.0.0.0/0"
        except:
            ip_bool = False
        
        try:
            ipv6_bool = responce["Ipv6Ranges"][0]["CidrIpv6"]=="::/0"
        except:
            ipv6_bool = False

        #全開放のポートのうち、80,443,25以外がないかチェック
        if any([ip_bool,ipv6_bool]):
            try:#tcpである時
                # print(responce)
                if all([
                        responce["FromPort"]==80,
                        responce["ToPort"]==80]):
                    security_check_result.append(True)
                elif all([
                        responce["FromPort"]==443,
                        responce["ToPort"]==443]):
                    security_check_result.append(True)
                elif all([
                        responce["FromPort"]==25,
                        responce["ToPort"]==25]):
                    security_check_result.append(True)
                else:
                    security_check_result.append(False)
            except: #IpProtocolが全てなどの場合
                # print(responce)
                security_check_result.append(False)
        else:
            pass
    if all(security_check_result)==False: #全部TrueならFalseとなり、elseが実行される
        return pycolor.RED_FLASH+"NG"+pycolor.END
    else:
        return "OK"

if __name__ == "__main__":

    instanceId = sys.argv[2]

    # pp.pprint(get_instances_info(ec2_client,instanceId))
    instance_info = get_instances_info(ec2_client,instanceId)

    cpu_burst = get_cpu_burst(ec2_client,instance_info)

    EIP = get_eip_info(ec2_client,instance_info)

    del_protect = get_del_protect(ec2_client,instance_info)

    vol_size,vol_type = get_vol_size_type(ec2_client,instance_info)

    cw_alarm = get_cloudwatch_alarms(cw_client,instanceId)

    iam_info = check_IAM(instance_info)

    # pp.pprint(iam_info)

    port_result = get_security_port(ec2_client,instance_info)

    Colomn_name1 = ["CPUバースト","CloudWatchアラート","セキュリティーグループ","EIP","削除保護","ディスクタイプ","IAMロール"]
    Colomn_name2 = ["AMI-ImageId","ディスク容量","インスタンスタイプ","アベイラビリティゾーン"]

    table1 = [cpu_burst,cw_alarm,port_result,EIP,del_protect,vol_type,iam_info]
    table2 = [instance_info["ImageId"],str(vol_size)+"GB",instance_info["InstanceType"],instance_info["AvailabilityZone"]]

    header = ["項目","結果"]
    table =[["CPUバースト",cpu_burst],
            ["CloudWatchアラート",cw_alarm],
            ["セキュリティーグループ",port_result],
            ["EIP",EIP],
            ["削除保護",del_protect],
            ["ディスクタイプ",vol_type],
            ["IAMロール",iam_info],
            ["AMI-ImageId",instance_info["ImageId"]],
            ["ディスク容量",str(vol_size)+"GB"],
            ["インスタンスタイプ",instance_info["InstanceType"]],
            ["アベイラビリティゾーン",instance_info["AvailabilityZone"]]]
    result = tabulate(table,header,tablefmt="grid")
    print(result)