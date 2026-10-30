# language: zh-CN
功能: CRM 后台 - 核对客户资料与 App 端提交一致

  # 注意：本用例是后台端，使用后台运营账号；
  # App 客户端账号是另一个（test_potato001@test.com / aa111111），见 app_update_profile.feature。
  背景:
    假如 后台打开页面[https://demo-console.crmtest.org/login]
    而且 等待[2]秒
    而且 在[input[placeholder='请输入邮箱或用户ID']]中输入[forestlin@pmonic.xyz]
    而且 在[input[type='password']]中输入[Aa@135246]
    而且 点击[text="登录"]
    而且 等待[3]秒

  @C_001
  场景: 客户管理-客户/代理列表，进入客户详情页核对邮箱显示 App 端提交的 potato@qq.com
    # 1. 进入 客户管理 - 客户/代理列表
    当 点击[text=客户管理]
    而且 等待[2]秒
    而且 点击[text=客户/代理列表]
    而且 等待[3]秒

    # 2. 用 App 端客户的手机号定位该客户
    #    这里不用邮箱：邮箱已被 App 端改成 potato@qq.com，原邮箱搜不到了
    而且 在[input[placeholder*='搜索']]中输入[554882589]
    而且 等待[2]秒

    # 3. 打开客户详情页（若列表行不是 tr，改成点击该手机号所在单元格）
    而且 点击[xpath=//tr[contains(., '554882589')]]
    而且 等待[3]秒

    # 4. 预期：详情页邮箱字段显示 App 端保存的 potato@qq.com
    那么 详情字段[邮箱]应显示[potato@qq.com]
    而且 页面文本应包含[potato@qq.com]
