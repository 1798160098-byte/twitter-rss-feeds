#!/usr/bin/env python3
"""
极简Twitter RSS生成器 - 修复版
使用 feedgen 库避免版本兼容问题
"""

import os
import sys
import json
import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import logging

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

class SimpleTwitterRSS:
    def __init__(self):
        """初始化"""
        self.instances = [
            'https://nitter.net',
            'https://nitter.kavin.rocks',
            'https://nitter.fdn.fr',
            'https://nitter.1d4.us',
            'https://nitter.privacydev.net',
        ]
        
        # 创建目录
        os.makedirs('feeds', exist_ok=True)
        os.makedirs('feeds/state', exist_ok=True)
        
        # 会话设置
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    
    def load_accounts(self) -> List[str]:
        """从accounts.txt加载账号列表"""
        accounts = []
        try:
            with open('accounts.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        accounts.append(line.lower())
            
            logger.info(f"从accounts.txt加载了 {len(accounts)} 个账号")
            return accounts
        except FileNotFoundError:
            logger.error("找不到 accounts.txt 文件")
            return []
    
    def load_state(self, username: str) -> Dict:
        """加载账号状态"""
        state_file = f'feeds/state/{username}.json'
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            'last_hash': None,
            'last_update': None,
            'last_count': 0,
            'failures': 0,
            'instance_used': None
        }
    
    def save_state(self, username: str, state: Dict):
        """保存账号状态"""
        with open(f'feeds/state/{username}.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def calculate_hash(self, tweets: List[str]) -> str:
        """计算推文哈希值"""
        if not tweets:
            return 'no_tweets'
        # 使用前3条推文（最新）计算哈希
        content = ''.join([t[:200] for t in tweets[:3]])
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def fetch_tweets(self, username: str) -> Tuple[List[str], str]:
        """抓取推文"""
        tweets = []
        instance_used = self.instances[0]
        
        for instance in self.instances:
            try:
                url = f"{instance}/{username}"
                logger.debug(f"尝试: {url}")
                
                response = self.session.get(url, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 查找推文内容
                    for selector in ['.tweet-content', '.tweet-body', '.timeline-item .tweet-content p']:
                        elements = soup.select(selector)
                        if elements:
                            for elem in elements[:15]:  # 最多15条
                                text = elem.get_text(strip=True)
                                if text and len(text) > 10:
                                    # 清理文本
                                    text = ' '.join(text.split())
                                    tweets.append(text)
                            break
                    
                    if tweets:
                        instance_used = instance
                        break
                        
            except Exception as e:
                logger.debug(f"实例 {instance} 失败: {str(e)[:50]}")
                continue
        
        return tweets, instance_used
    
    def generate_rss(self, username: str, tweets: List[str], instance: str) -> str:
        """生成RSS XML（使用feedgen库）"""
        fg = FeedGenerator()
        
        # 设置feed基本信息
        fg.title(f'Twitter - @{username}')
        fg.link(href=f'https://twitter.com/{username}', rel='alternate')
        fg.description(f'自动生成的Twitter RSS - 最后更新: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}')
        fg.language('en')
        fg.lastBuildDate(datetime.now(timezone.utc))
        fg.generator('Simple Twitter RSS Generator')
        
        if tweets:
            for idx, text in enumerate(tweets[:20]):  # 最多20条
                fe = fg.add_entry()
                tweet_id = hashlib.md5(f"{username}_{text}".encode()).hexdigest()[:8]
                
                # 标题（截断处理）
                if len(text) > 80:
                    title = f'{text[:80]}...'
                else:
                    title = text
                
                fe.title(title)
                fe.description(text)
                fe.link(href=f'https://twitter.com/{username}/status/{tweet_id}', rel='alternate')
                fe.guid(f'twitter_{username}_{tweet_id}', permalink=False)
                fe.pubDate(datetime.now(timezone.utc))
        else:
            # 没有推文时
            fe = fg.add_entry()
            placeholder_id = f'placeholder_{username}_{int(time.time())}'
            
            fe.title(f'@{username} - 暂无新推文')
            fe.description(f'更新时间: {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}')
            fe.link(href=f'https://twitter.com/{username}', rel='alternate')
            fe.guid(placeholder_id, permalink=False)
            fe.pubDate(datetime.now(timezone.utc))
        
        # 生成RSS XML
        return fg.rss_str(pretty=True).decode('utf-8')
    
    def process_account(self, username: str) -> bool:
        """处理单个账号，返回是否需要更新"""
        logger.info(f"处理账号: @{username}")
        
        # 加载状态
        state = self.load_state(username)
        last_hash = state.get('last_hash')
        failures = state.get('failures', 0)
        
        # 如果连续失败3次，跳过（避免浪费资源）
        if failures >= 3:
            logger.info(f"跳过: @{username} - 连续失败{failures}次")
            return False
        
        # 抓取推文
        tweets, instance_used = self.fetch_tweets(username)
        current_hash = self.calculate_hash(tweets)
        current_count = len(tweets)
        
        # 判断是否需要更新
        needs_update = False
        reason = ""
        
        if not last_hash:
            # 第一次运行
            needs_update = True
            reason = "首次运行"
        elif current_hash != last_hash:
            # 推文有变化
            needs_update = True
            reason = f"推文更新 ({state.get('last_count', 0)} → {current_count})"
        elif current_count == 0 and state.get('last_count', 0) == 0:
            # 保持活跃：每12小时更新一次空状态
            last_update = state.get('last_update')
            if last_update:
                try:
                    last_time = datetime.fromisoformat(last_update)
                    hours_since = (datetime.now() - last_time).total_seconds() / 3600
                    if hours_since > 12:
                        needs_update = True
                        reason = "保活更新 (12h)"
                except:
                    pass
        
        if needs_update:
            logger.info(f"需要更新: {reason}")
            
            # 生成RSS
            rss_content = self.generate_rss(username, tweets, instance_used)
            
            # 保存RSS文件
            with open(f'feeds/{username}.rss', 'w', encoding='utf-8') as f:
                f.write(rss_content)
            
            # 更新状态
            new_state = {
                'last_hash': current_hash,
                'last_update': datetime.now().isoformat(),
                'last_count': current_count,
                'failures': 0 if tweets else (failures + 1),
                'instance_used': instance_used,
                'update_reason': reason
            }
            self.save_state(username, new_state)
            
            return True
        else:
            logger.info(f"跳过: @{username} - 无变化")
            return False
    
    def generate_urls_file(self, github_username: str):
        """生成URL列表文件"""
        accounts = self.load_accounts()
        
        if not accounts:
            logger.warning("没有找到账号，跳过生成URL列表")
            return
        
        urls_content = f"""# Twitter RSS URLs
# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# GitHub用户: {github_username}
# 总账号数: {len(accounts)}
#
# 使用方法:
# 1. 复制下面的URL到n8n的RSS Feed Trigger节点
# 2. 设置检查频率（推荐10-15分钟）
# 3. 如需添加新博主，在accounts.txt中添加用户名即可

"""
        
        for username in accounts:
            url = f"https://raw.githubusercontent.com/{github_username}/twitter-rss-feeds/main/feeds/{username}.rss"
            web_url = f"https://github.com/{github_username}/twitter-rss-feeds/blob/main/feeds/{username}.rss?raw=true"
            
            urls_content += f"# @{username}\n"
            urls_content += f"主URL: {url}\n"
            urls_content += f"备用URL: {web_url}\n"
            urls_content += "-" * 60 + "\n\n"
        
        # 保存文件
        with open('urls.txt', 'w', encoding='utf-8') as f:
            f.write(urls_content)
        
        logger.info(f"已生成URL列表: urls.txt ({len(accounts)}个账号)")
    
    def run(self):
        """运行主程序"""
        start_time = time.time()
        accounts = self.load_accounts()
        
        if not accounts:
            logger.error("没有找到任何账号，请检查accounts.txt文件")
            return 0, 0
        
        logger.info(f"开始处理 {len(accounts)} 个账号")
        
        updated_count = 0
        for username in accounts:
            try:
                if self.process_account(username):
                    updated_count += 1
                # 短暂延迟，避免请求过快
                time.sleep(1)
            except Exception as e:
                logger.error(f"处理账号 @{username} 时出错: {e}")
                continue
        
        elapsed = time.time() - start_time
        logger.info(f"处理完成! 更新了 {updated_count}/{len(accounts)} 个账号，耗时 {elapsed:.1f}秒")
        
        return updated_count, len(accounts)

def main():
    """主函数入口"""
    # 检查命令行参数
    force_update = '--force' in sys.argv
    
    if force_update:
        logger.info("强制更新模式")
    
    generator = SimpleTwitterRSS()
    
    if force_update:
        # 强制更新：清空所有状态
        accounts = generator.load_accounts()
        for username in accounts:
            state = generator.load_state(username)
            state['last_hash'] = None
            generator.save_state(username, state)
        logger.info("已清除所有状态，下次运行将强制更新")
        return
    
    # 正常运行
    updated, total = generator.run()
    
    # 生成URL列表
    github_user = os.getenv('GITHUB_REPOSITORY_OWNER', 'YOUR_USERNAME')
    generator.generate_urls_file(github_user)
    
    # 设置GitHub Actions输出
    if os.getenv('GITHUB_ACTIONS'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'updated={updated > 0}\n')
            f.write(f'updated_count={updated}\n')
            f.write(f'total_accounts={total}\n')
    
    # 如果没有更新，返回非零退出码（让GitHub Actions知道无需提交）
    if updated == 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
