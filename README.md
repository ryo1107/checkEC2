# install

```
$ pip install tabulate boto3
```

# need

```
~/.aws/config
~/.aws/credentials
```

# run

```
$ python checkEC2.py profile InstanceId (resion_name)
```

# output

| 項目                   | 結果                  |
|------------------------|-----------------------|
| CPUバースト            | OK-Disable            |
| CloudWatchアラート     |  None                 |
| セキュリティーグループ |  NG                   |
| EIP                    | OK                    |
| 削除保護               | Enable                |
| ディスクタイプ         | マグネティック        |
| IAMロール              |  NG                   |
| AMI-ImageId            | ami-0c3fd0f5d33134a76 |
| ディスク容量           | 8GB                   |
| インスタンスタイプ     | t2.micro              |
| アベイラビリティゾーン | ap-northeast-1a       |
