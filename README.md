# SNOWCTF_V1.0

一个基于django开发的CTF竞赛平台。
主要功能：CTF比赛、漏洞靶场、网络安全夺旗比赛、动态FLAG、数据大屏、作弊监测、动态分数、团队赛、个人赛、自动化报名

作者：snow
后端：Python3.11+Django5.1
前端：Bootstrap+[iznoe](https://github.com/Hopetree/izone "iznoe")
安装及使用指导手册：https://www.secsnow.cn/blog/subject/6/


## 界面介绍

####主页面

![主页面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228164549.png)

####比赛界面

![比赛界面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228164740.png)

####答题界面
![比赛界面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228164944.png)

####排行榜单
![比赛界面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228165320.png)

####自动化报名
![比赛界面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228170352.png)

![比赛界面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228170423.png)

####数据大屏
![比赛界面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img801a18cc9b1fd1aa9ca7f7a29947ab8.png)

####后台管理
![比赛界面](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228170004.png)

## 动态分数算法
比赛分数会根据解题次数动态调整，跟解题快慢无关
![分数](https://raw.githubusercontent.com/TheMoonu/TheMoonu/main/img20250228171202.png)
```python
points = max(
    minimum_points, 
    initial_points * (3 + min(solve_count, 1)) / (3 + solve_count)
)
```
