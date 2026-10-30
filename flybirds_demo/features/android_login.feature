# language: zh-CN
功能: WeTrade App - 登录功能测试

  场景: 验证使用正确的账号密码成功登录
    # 0. 清空 App 数据，避免上次登录态影响（已登录时首页没有登录入口）
    假如 清除应用数据[com.wetrade.crm.trial]

    # 1. 启动 App（雷电精简镜像无 monkey，用自定义步骤指定 Activity）
    当 启动应用[com.wetrade.crm.trial][com.wetrade.crm.MainActivity]
    而且 页面渲染完成出现元素[name=登录/注册]

    # 2. 进入登录页（输入框的占位文案在 text 属性上）
    而且 点击[name=登录/注册]
    而且 页面渲染完成出现元素[text=请输入邮箱或手机号]

    # 3. 输入账号
    而且 在[text=请输入邮箱或手机号]中输入[test_potato001@test.com]

    # 4. 输入密码
    而且 在[text=请输入密码]中输入[aa111111]

    # 5. 点击登录
    而且 点击[name=登录]
    而且 等待[10]秒

    # 6. 登录成功后首页不再有登录入口
    而且 不存在[name=登录/注册]的元素
