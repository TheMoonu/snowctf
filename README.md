# SNOWCTF_V1.0(个人版)
一个基于django开发的CTF竞赛平台。
主要功能：CTF比赛、漏洞靶场、网络安全夺旗比赛、动态FLAG、数据大屏、作弊监测、动态分数、团队赛、个人赛、自动化报名。

目标：致力于共创、共享网络安全学习环境。

后端：Python3.11+Django5.

前端：Bootstrap

安装及使用指导：[SNOWCTF_V1.0(个人版)安装及使用指导手册](https://www.secsnow.cn/blog/subject/6/)

页面UI具体参考：[SECSNOW_V1.0(专业版)](https://www.secsnow.cn/snowlab/)

PS：本开源项目为个人版，主要为个人或者小型团队提供CTF竞赛需求。如果您是中大型安全团队技术专家、中高等教育工作者、中高等学校院校级网络安全竞赛组织者、社会组织或者企业安全部门等人员，想要通过一个产品或者软件为您所在的组织人员提供一个网络安全综合学习平台，建议您了解我们的网络安全综合学习平台[SECSNOW_V1.0(专业版)](https://www.secsnow.cn/)

专业版整合了贴合中文操作逻辑的CTF竞赛系统、知识竞赛系统、漏洞靶场练习系统、WIKI知识库管理系统、工具管理及招聘岗位发布等核心功能模块，全面覆盖竞赛组织、技能实训、知识沉淀、资源管理与人才对接等多元需求。为持续保障项目的稳定运维、功能迭代与技术支持，我们通过著作权授权的方式筹集必要经费，既能支撑团队投入更多精力优化产品体验、响应用户反馈，也能确保长期为用户提供更优质、可靠且可持续的服务支持。您的支持就是我们技术开源的动力！谢谢！

交流、学习、合作、专业版部署了解联系：qun：base64（5omj5omj5a2m5Lmg5Lqk5rWB576kNTE3OTI5NDU4）、邮箱：flechazo890@gmail.com

## Saas竞赛服务
当然如果您不想耗费时间、精力及金钱去搭建竞赛系统，[SECSNOW_竞赛中心](https://www.secsnow.cn/ctf/)提供了限时免费的Saas竞赛服务，用户可在平台自定义比赛，本平台提供比赛的容器服务，不需要在单独购买服务器，比赛创建者可对比赛进行任何形式的管理，包括报名、人员、队伍、赛题、作弊监测、计分及排名管理等。


## 动态分数算法
比赛分数会根据解题次数动态调整，跟解题快慢无关

![分数](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228171202.png)

```python
points = max(
    minimum_points, 
    initial_points * (3 + min(solve_count, 1)) / (3 + solve_count)
)
```

## 界面介绍

#### 数据大屏
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img801a18cc9b1fd1aa9ca7f7a29947ab8.png)

#### 主页面

![主页面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228164549.png)

#### 比赛界面

![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228164740.png)

#### 答题界面
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228164944.png)

#### 排行榜单
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228165320.png)

#### 自动化报名
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228170352.png)

![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228170423.png)

#### 后台管理
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228170004.png)


## 其它声明
本项目开发过程中使用了部分[iznoe](https://github.com/Hopetree/izone "iznoe")、[simpleui](https://github.com/newpanjing/simpleui)项目代码及架构，非常感谢！
