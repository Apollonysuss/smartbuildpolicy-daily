name: 手动挖掘历史

on:
  workflow_dispatch:

permissions:
  contents: write

jobs:
  history-job:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - run: pip install requests
    
    - name: 运行历史挖掘
      env:
        DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
      run: python get_history.py
      
    - name: 保存结果
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add data.json
        git commit -m "History update" || echo "无新数据"
        
        # 👇【关键修改】上传前，先拉取最新代码，防止冲突
        git pull --rebase
        
        git push
