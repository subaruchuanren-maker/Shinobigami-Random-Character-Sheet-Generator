import pandas as pd
import random
import re
import json
import math 
from typing import List, Dict, Any, Set, Optional

# =======================================================
# 1. 定数とルールの定義
# =======================================================

RANK_SLOTS = {
    '中忍': {'ninpo': 5, 'skill': 6}, '中忍頭': {'ninpo': 6, 'skill': 6},
    '上忍': {'ninpo': 7, 'skill': 7}, '上忍頭': {'ninpo': 8, 'skill': 7},
}

RANK_POINTS = {
    '中忍頭': 10, '上忍': 30, '上忍頭': 80
}
# ★ 最終決定版: 背景修得上限 (長所/弱点) の定義
RANK_BG_LIMITS = {
    '中忍': {'chosho': 2, 'jakuten': 2}, 
    '中忍頭': {'chosho': 3, 'jakuten': 3},
    '上忍': {'chosho': 4, 'jakuten': 4}, 
    '上忍頭': {'chosho': 5, 'jakuten': 5},
}
SCHOOL_SERIES_SKILL_MAP = {
    '斜歯系列': '器術', '鞍馬系列': '体術', 'ハグレ系列': '忍術',
    '比良坂系列': '謀術', '御斎系列': '戦術', '隠忍系列': '妖術',
    '古流': None, '汎用': None, '屍衣': '妖術', 
}
# 奥義リスト (ID付き)
OUGIES_MASTER = [
    {'ID': 1, '名前': "クリティカルヒット"}, {'ID': 2, '名前': "範囲攻撃"}, 
    {'ID': 3, '名前': "完全成功"}, {'ID': 4, '名前': "判定妨害"}, 
    {'ID': 5, '名前': "絶対防御"}, {'ID': 6, '名前': "不死身"}, 
    {'ID': 7, '名前': "追加忍法"}
]
# 忍具リスト (ID付き)
NINGU_MASTER = [
    {'ID': 1, '名前': "兵糧丸"}, {'ID': 2, '名前': "神通丸"}, 
    {'ID': 3, '名前': "遁甲符"}
]

# =======================================================
# 2. NPC クラスの定義
# =======================================================

class NPC:
    """生成されたNPCのデータを保持するクラス"""
    def __init__(self, char_id: int, name: str, rank: str, school: str, kouseki: int):
        self.連番 = char_id 
        self.氏名 = name
        self.階級 = rank
        self.所属流派 = school
        self.功績点 = kouseki

        self.流派系列: Optional[str] = None
        self.背景 = [] # 内部処理用 ({'種別': '長所', '名前': '名前', '功績点': 3})
        self.忍法 = []
        self.修得特技: Set[str] = set()
        self.奥義 = []
        self.忍具 = {} 
        
        # CSV出力用のリスト
        self.背景_list: List[Dict[str, Any]] = []
        self.忍法_list: List[Dict[str, Any]] = []
        self.特技_list: List[Dict[str, Any]] = []
        self.奥義_list: List[Dict[str, Any]] = []
        self.忍具_list: List[Dict[str, Any]] = []
        
    def to_dict(self) -> Dict[str, Any]:
        """結合CSVに残すための基本データ"""
        return {
            '連番': self.連番, 
            '氏名': self.氏名,
            '最終功績点': self.功績点,
        }

# =======================================================
# 3. NPCGenerator クラスの定義 (メインロジック)
# =======================================================

class NPCGenerator:
    """NPCの生成ロジックとマスターデータ管理を行うクラス"""

    def __init__(self):
        self.master = self._load_master_data() 
        self._initialize_master_data()
        self.RANK_SLOTS = RANK_SLOTS
        self.RANK_BG_LIMITS = RANK_BG_LIMITS

    # ★ 修正1: 静的メソッドからインスタンスメソッドへ変更 (selfアクセスが必要なため)
    def select_random_skill(self, required_skill_str: str) -> str:
        """
        忍法マスタの指定特技欄の文字列に基づき、ランダムに1つの特技を選択する。
        """
        # クラス変数にアクセス
        all_skills = self.all_skills
        skill_field_map = self.skill_field_map
        rule = required_skill_str.strip()
        
        if pd.isna(required_skill_str) or required_skill_str.strip() in ['なし', '']:
            return 'なし'

        # --- 1. 分野指定の場合 (例: '分野:器術', '好きな妖術') ---
        # '分野:' または '好きな' で始まり、末尾に「術」があるパターンを抽出
        # 例: "分野:器術" -> "器術", "好きな妖術" -> "妖術"
        match_field = re.search(r'(?:分野:|好きな)?(.+術)', rule)
        
        if match_field:
            # `match_field.group(1)` には '器術' や '妖術' が入る
            target_field = match_field.group(1).strip()
            
            # 指定分野に属する特技のリストを抽出
            # skill_field_map (特技名:分野名) を使用してフィルタリング
            field_skills = [skill for skill, field in skill_field_map.items() if field == target_field]
            
            if field_skills:
                return random.choice(field_skills)
            else:
                # フィールド名が不正・該当特技なしの場合
                return 'なし'

        # ★ 修正: '自由'の場合はここでランダム特技を決定する
        elif rule == '自由':
            return random.choice(all_skills) if all_skills else 'なし'

        # '可変'はルール文字列をそのまま返す (特技修得フェーズで処理)
        elif rule == '可変':
            return rule

        # 3. 特定特技リストの場合 (例: '《針術》《隠蔽術》《異形化》')
        # 《》を削除し、特技名を抽出
        skills_list = [s.strip().replace('《', '').replace('》', '') for s in required_skill_str.split('》') if s.strip()]
    
        # 候補からランダムに1つ選択
        if skills_list:
            # 特技マスタに存在する特技のみから選ぶ（念のため）
            valid_skills = [s for s in skills_list if s in skill_field_map]
            if valid_skills:
                return random.choice(valid_skills)
            else:
                return 'なし'
            
        return 'なし'

    def _load_master_data(self) -> Dict[str, pd.DataFrame]:
        """Excelファイルを読み込み、前処理を実行"""
        # このメソッドは変更なし (省略)
        file_sheet_map = {
            '背景': ('背景.xlsx', '背景_マスタ'),
            '忍法': ('忍法.xlsx', '忍法_マスタ'),
            '特技': ('特技.xlsx', '特技_マスタ'),
            '流派': ('流派.xlsx', '流派_マスタ'),
        }
        
        master_data = {}
        for key, (file_name, sheet_name) in file_sheet_map.items():
            try:
                try:
                    master_data[key] = pd.read_excel(file_name, sheet_name=sheet_name)
                except Exception:
                    # Excelファイルの読み込みに失敗した場合、CSVファイル名（Excel名 - シート名.csv）を試す
                    master_data[key] = pd.read_csv(f'{sheet_name}.csv', encoding='utf_8_sig')
            except Exception as e:
                raise Exception(f"マスターファイル読み込みエラー: {e}\nファイル名:「{file_name}」または「{file_name} - {sheet_name}.csv」が正しいか確認してください。")
        return master_data
    
    def _initialize_master_data(self):
        """マスターデータの前処理と特殊データの準備 (変更なし)"""
        # 特技データ
        self.skill_field_map = self.master['特技'].set_index('名前')['分野'].to_dict()
        self.field_skills = self.master['特技'].groupby('分野')['名前'].apply(list).to_dict()
        self.all_skills = list(self.skill_field_map.keys())
        self.general_schools = self.master['流派'][self.master['流派']['流派名'] != '汎用'].copy()
        
        # 忍法データ
        df_np = self.master['忍法'].copy()
        df_np.rename(columns={'流派種別': '種別', '下位流派': '流派'}, inplace=True, errors='ignore')
        df_np['指定特技'] = df_np['指定特技'].astype(str).str.strip() 
        
        # ★★★ 修正1: 秘伝も含む全忍法を保持 (特例用) ★★★
        self.all_ninpo_master = df_np.copy()
        # ★★★ ここまで ★★★

        # 通常修得用の秘伝を除外
        df_np = df_np[df_np['種別'].astype(str).str.strip() != '秘伝'].copy()
        sekkin_ninpo_data = df_np[df_np['名前'].astype(str).str.strip() == '接近戦攻撃※']
        if sekkin_ninpo_data.empty: raise ValueError("忍法マスタに「接近戦攻撃※」が見つかりません。")
        self.ninpo_sekkin = sekkin_ninpo_data.iloc[0].copy()
        self.master['忍法'] = df_np[df_np['名前'].astype(str).str.strip() != '接近戦攻撃※'].copy()
        
        # 流派データ
        df_sc = self.master['流派'].copy()
        df_sc.rename(columns={'流派所属条件': '加入必須特技', '流派所属条件（テキスト）': '加入必須特技'}, inplace=True, errors='ignore')
        if '加入必須特技' in df_sc.columns:
            df_sc['加入必須特技'] = df_sc['加入必須特技'].astype(str).str.strip()
        
        # 背景データ
        self.df_bg_master = self.master['背景'].copy()
        self.df_bg_master['功績点'] = pd.to_numeric(
            self.df_bg_master['功績点'].astype(str)
            .str.replace(r'\(.*\)', '', regex=True)
            .str.strip().replace('なし', 0), 
            errors='coerce'
        ).fillna(0).astype(int)
        
        # '修得制限'と'コスト条件'カラムの存在確認と前処理
        if '修得制限' not in self.df_bg_master.columns:
             print("⚠️ 警告: 背景マスターに'修得制限'カラムが見つかりません。制限チェックは無効化されます。")
             self.df_bg_master['修得制限'] = '汎用' 
        if 'コスト条件' not in self.df_bg_master.columns:
             print("⚠️ 警告: 背景マスターに'コスト条件'カラムが見つかりません。コスト変動は無効化されます。")
             self.df_bg_master['コスト条件'] = 'なし' 
             
        self.df_bg_chosho = self.df_bg_master[self.df_bg_master['種別'] == '長所'].copy()
        self.df_bg_jakuten = self.df_bg_master[self.df_bg_master['種別'] == '弱点'].copy()

        # IDマッピング
        self.ninpo_id_map = self.master['忍法'].set_index('名前')['忍法ID'].to_dict()
        self.skill_id_map = self.master['特技'].set_index('名前')['特技ID'].to_dict()
        self.bg_id_map = self.df_bg_master.set_index('名前')['背景ID'].to_dict()
        
        # 奥義と忍具のIDマッピング
        self.ougi_id_map = {o['名前']: o['ID'] for o in OUGIES_MASTER}
        self.ningu_id_map = {n['名前']: n['ID'] for n in NINGU_MASTER}
        self.ougi_names = [o['名前'] for o in OUGIES_MASTER]
        self.ningu_names = [n['名前'] for n in NINGU_MASTER]


    # --- 背景の修得制限チェックメソッド (NOT構文の解析を修正) ---
    def _check_background_restriction(self, npc: NPC, rule_str: str) -> bool:
        rule = str(rule_str).strip()
        if not rule or rule in ['汎用', 'なし', '－', 'nan']:
            return True
        
        # 取得済みの背景の名前のセット
        acquired_bg_names = {bg['名前'] for bg in npc.背景}
        
        # 条件を '+' で分割し、いずれかがTrueならOK (OR条件)
        conditions = [r.strip('《》').strip('/').strip('(').strip(')') for r in rule.split('+')]
        
        # NPCの流派名と系列名を安全に取得・整形
        npc_shuzoku = str(npc.所属流派).strip()
        npc_series = str(npc.流派系列).strip() if npc.流派系列 else '' 
        
        for condition in conditions:
            condition = condition.strip()
            if not condition: continue

            # A. HAVE: 条件チェック
            if condition.startswith('HAVE:'):
                required_name = condition[len('HAVE:'):].strip()
                if required_name in acquired_bg_names:
                    return True # OR条件: 一つ満たした
                continue 

            # B. NOT 条件チェック
            is_not_condition = condition.startswith('NOT')
            
            if is_not_condition:
                # 'NOT'の3文字を削除後、先頭のコロン':'と前後の空白を削除してチェックルールを取得
                check_rule = condition[3:].lstrip(':').strip() 
            else:
                check_rule = condition
            
            if not check_rule: continue # ルール文字列が空になった場合はスキップ

            # check_ruleとNPCの流派/系列を比較
            is_match = check_rule == npc_shuzoku or check_rule == npc_series
            
            if is_not_condition:
                if not is_match:
                    # NOT [Rule] かつ NOT マッチ => 満たした
                    return True
            else:
                if is_match:
                    # [Rule] かつ マッチ => 満たした
                    return True
        
        # どの条件も満たされなかった
        return False
        
    # --- コスト条件を考慮した功績点計算メソッド (変更なし) ---
    def _calculate_effective_cost(self, npc: NPC, base_cost: int, cost_rule_str: str) -> int:
        # このメソッドは変更なし (省略)
        rule = str(cost_rule_str).strip()
        if not rule or rule in ['汎用', 'なし', '－', 'nan']:
            return base_cost

        # 1. '|' 区切りの条件/固定値形式 (長所: 固定値)
        # 例: 麝香会総合病院|4 (所属していればコストは4)
        if '|' in rule:
            condition_str, value_str = rule.split('|', 1)
            conditions = [s.strip('《》') for s in condition_str.split('+')]
            
            if any(c == npc.所属流派 or c == npc.流派系列 for c in conditions):
                try:
                    return int(value_str.strip())
                except ValueError:
                    pass 
        
        # 2. '/' 区切りの条件/半額形式 (長所: 半額)
        # 例: 麝香会総合病院/ (所属していれば半額、端数切り上げ)
        if '/' in rule:
            parts = rule.split('/')
            condition_str = parts[0]
            
            is_half_rule = len(parts) == 2 and parts[1].strip() == '' or \
                            len(parts) > 1 and parts[1].strip().upper() in ['半額', '1/2', 'ハナガク/2']
                            
            if is_half_rule:
                conditions = [s.strip('《》') for s in condition_str.split('+')]

                if any(c == npc.所属流派 or c == npc.流派系列 for c in conditions):
                    # ★ 端数切り上げ (ceil) を適用
                    return math.ceil(base_cost / 2)
        
        # 3. 加算/減算形式 (弱点)
        # 例: 御斎系列+1
        match = re.match(r'^(.+?)([+-])(\d+)$', rule)
        if match:
            condition_str, operator, amount_str = match.groups()
            amount = int(amount_str)
            
            conditions = [s.strip('《》') for s in condition_str.split('+')]
            
            if any(c == npc.所属流派 or c == npc.流派系列 for c in conditions):
                return base_cost + (amount if operator == '+' else -amount)
        
        # どの条件にも合致しない場合は基本コスト
        return base_cost
    
    def _determine_backgrounds(self, npc: NPC):
        # 1. 階級に基づいた上限を取得 (外部のRANK_BG_LIMITS定数を参照)
        limits = RANK_BG_LIMITS.get(npc.階級, {'chosho': 2, 'jakuten': 2})
        max_jakuten_limit = limits['jakuten']
        max_chosho_limit = limits['chosho']

        # --- 1. 弱点の処理 ---
        while True:
            current_jakuten_count = len([bg for bg in npc.背景 if bg['種別'] == '弱点'])
            
            # 取得上限に達していたら終了
            if current_jakuten_count >= max_jakuten_limit:
                break
            
            # 継続判定: 1つ増えるごとに継続率を25%下げる (0個:100%継続, 1個:75%継続, 2個:50%継続...)
            if current_jakuten_count > 0:
                if random.random() < (current_jakuten_count * 0.25):
                    break # 確率判定により、上限に達する前に終了

            # 弱点候補の抽出
            available_jakuten = self.df_bg_jakuten[
                self.df_bg_jakuten.apply(
                    lambda r: self._check_background_restriction(npc, str(r.get('修得制限', '汎用'))), 
                    axis=1
                )
            ].copy()
            
            acquired_jakuten_names = {bg['名前'] for bg in npc.背景 if bg['種別'] == '弱点'}
            available_jakuten = available_jakuten[
                ~available_jakuten['名前'].astype(str).str.strip().isin(acquired_jakuten_names)
            ].copy()

            if available_jakuten.empty:
                break
            
            chosen_jakuten_data = available_jakuten.sample(n=1).iloc[0]
            final_cost = self._calculate_effective_cost(npc, chosen_jakuten_data['功績点'], str(chosen_jakuten_data.get('コスト条件', 'なし')))
            
            npc.功績点 += final_cost 
            
            bg_name = chosen_jakuten_data['名前'].strip()
            bg_id = chosen_jakuten_data.get('背景ID', 0)

            npc.背景.append({'種別': '弱点', '名前': bg_name, '功績点': -final_cost})
            
            # CSV出力用 (all_bg_data に追加される元データ)
            npc.背景_list.append({
                'キャラID': npc.連番, 
                '背景ID': bg_id, 
                '背景名': bg_name,
                '種別': '弱点',
                '功績点_変動': final_cost
            })

        # --- 2. 長所の処理 ---
        while True:
            current_chosho_count = len([bg for bg in npc.背景 if bg['種別'] == '長所'])
            
            # 取得上限に達していたら終了
            if current_chosho_count >= max_chosho_limit:
                break
            
            # 継続判定: 弱点と同様に1つごとに継続率25%減少
            if current_chosho_count > 0:
                if random.random() < (current_chosho_count * 0.25):
                    break

            # コスト計算済みのコピーを作成
            df_chosho_calc = self.df_bg_chosho.copy()
            df_chosho_calc['EffectiveCost'] = df_chosho_calc.apply(
                lambda r: self._calculate_effective_cost(npc, r['功績点'], str(r.get('コスト条件', 'なし'))),
                axis=1
            )

            # 現在の功績点で買える、かつ未取得、かつ修得制限をパスするものに絞る
            available_chosho = df_chosho_calc[
                (df_chosho_calc['EffectiveCost'] <= npc.功績点) & 
                (~df_chosho_calc['名前'].str.strip().isin({bg['名前'] for bg in npc.背景}))
            ].copy()

            available_chosho = available_chosho[
                available_chosho.apply(lambda r: self._check_background_restriction(npc, str(r.get('修得制限', '汎用'))), axis=1)
            ]

            if available_chosho.empty:
                break

            chosen_chosho_data = available_chosho.sample(n=1).iloc[0]
            chosho_cost = chosen_chosho_data['EffectiveCost'] 
            
            npc.功績点 -= chosho_cost
            bg_name = chosen_chosho_data['名前'].strip()
            bg_id = chosen_chosho_data.get('背景ID', 0)

            npc.背景.append({'種別': '長所', '名前': bg_name, '功績点': chosho_cost})
            
            # CSV出力用
            npc.背景_list.append({
                'キャラID': npc.連番, 
                '背景ID': bg_id, 
                '背景名': bg_name,
                '種別': '長所',
                '功績点_変動': -chosho_cost
            })
            
    # --- 忍法決定ロジック ---
    def _acquire_ninpo_by_rule(self, npc: NPC, rule: str):
        rule = rule.strip()
        if not rule or rule in ['なし', '－']: return

        rule_info = re.match(r'(種別|流派):([^:]+):(\d+)', rule)
        
        if rule_info:
            rule_type, value, count_str = rule_info.groups()
            value = value.strip()
            count = int(count_str)
            
            # ★★★ 修正2: 全ての忍法マスターデータから候補を絞り込む ★★★
            candidates = self.all_ninpo_master.copy()
            # ★★★ ここまで ★★★
            
            if rule_type == '種別':
                candidates = candidates[candidates['種別'].astype(str).str.strip() == value]
            elif rule_type == '流派':
                candidates = candidates[candidates['流派'].astype(str).str.strip() == value]
            
            acquired_names = {n['名前'] for n in npc.忍法}
            candidates = candidates[~candidates['名前'].astype(str).str.strip().isin(acquired_names)]
            
            if not candidates.empty:
                chosen_ninpo_data = candidates.sample(n=min(count, len(candidates)), replace=False)
                for _, ninpo_data in chosen_ninpo_data.iterrows():
                    self._add_ninpo(npc, ninpo_data, is_overlimit=True)
        else:
            ninpo_data = self.master['忍法'][self.master['忍法']['名前'].astype(str).str.strip() == rule.strip('《》')]
            if not ninpo_data.empty:
                self._add_ninpo(npc, ninpo_data.iloc[0], is_overlimit=True)

    def _apply_ninpo_special_exceptions(self, npc: NPC):
        # このメソッドは変更なし (省略)
        chosen_bg_names = {bg['名前'] for bg in npc.背景}
        
        chosen_bg_data = self.df_bg_master[
            self.df_bg_master['名前'].astype(str).str.strip().isin(chosen_bg_names)
        ].copy()
        
        for _, bg_row in chosen_bg_data.iterrows():
            rule = bg_row.get('忍法特例')
            if pd.notna(rule) and str(rule).strip() not in ['なし', '－']:
                self._acquire_ninpo_by_rule(npc, str(rule))

    def _get_ninpo_candidates(self, npc: NPC) -> pd.DataFrame:
        # このメソッドは変更なし (省略)
        candidates = self.master['忍法'][
            (self.master['忍法']['階級制限'].astype(str).str.strip().isin(['－', npc.階級]))
        ].copy()
        candidates = candidates[
            (candidates['流派'].astype(str).str.strip() == npc.所属流派) | 
            (candidates['流派'].astype(str).str.strip().isin(['汎用', '古流', '異種']))
        ].copy()
        acquired_names = {n['名前'] for n in npc.忍法}
        candidates = candidates[~candidates['名前'].astype(str).str.strip().isin(acquired_names)]
        return candidates

    def _acquire_ninpo_from_candidates(self, npc: NPC, candidates: pd.DataFrame, count: int):
        # このメソッドは変更なし (省略)
        acquired_names = {n['名前'] for n in npc.忍法}
        candidates = candidates[~candidates['名前'].astype(str).str.strip().isin(acquired_names)]
        if candidates.empty: return
        current_ninpo_count = len([n for n in npc.忍法 if n.get('枠消費なし') is not True and n.get('POST_PROCESS') is not True])
        ninpo_limit = RANK_SLOTS[npc.階級]['ninpo']
        actual_count = min(count, ninpo_limit - current_ninpo_count)
        if actual_count <= 0: return
        chosen_ninpo_data = candidates.sample(n=actual_count, replace=False)
        for _, ninpo_data in chosen_ninpo_data.iterrows():
            self._add_ninpo(npc, ninpo_data, is_overlimit=False)

    # ★ 修正2: 忍法取得時に指定特技をランダム決定するロジックを追加
    def _add_ninpo(self, npc: NPC, ninpo_data: pd.Series, is_overlimit: bool):
        # マスタデータ上の指定特技ルール文字列を取得
        required_skill_rule = ninpo_data['指定特技'].strip() if pd.notna(ninpo_data['指定特技']) else 'なし'
        
        # ★ ここで、ルールに基づき、実際に修得する特技名をランダムで決定する
        designated_skill = self.select_random_skill(required_skill_rule)

        ninpo_name = ninpo_data['名前'].strip()
        ninpo_id = ninpo_data['忍法ID']
        ninpo_type = ninpo_data['タイプ'].strip() if pd.notna(ninpo_data['タイプ']) else 'その他'
        
        # 内部処理用
        npc.忍法.append({
            '名前': ninpo_name, 'ID': ninpo_id, '指定特技': designated_skill, # ランダム決定された特技名
            '枠消費なし': is_overlimit, 'タイプ': ninpo_type
        })
        
        # 外部出力用
        npc.忍法_list.append({
            'キャラID': npc.連番,
            '忍法ID': ninpo_id,
            '忍法名': ninpo_name,
            '指定特技': designated_skill # ランダム決定された特技名
        })
        
    def _determine_ninpo(self, npc: NPC):
        # このメソッドは変更なし (省略)
        self._add_ninpo(npc, self.ninpo_sekkin, is_overlimit=True) 
        ninpo_limit = RANK_SLOTS[npc.階級]['ninpo']
        current_ninpo_count = len([n for n in npc.忍法 if n.get('枠消費なし') is not True and n.get('POST_PROCESS') is not True])
        remaining_slots = ninpo_limit - current_ninpo_count
        if remaining_slots > 0:
            candidate_ninpo = self._get_ninpo_candidates(npc)
            self._acquire_ninpo_from_candidates(npc, candidate_ninpo, remaining_slots)

    # --- 特技決定ロジック（_parse_skill_acquisition_ruleは変更なし） ---
    def _parse_skill_acquisition_rule(self, rule_str: str) -> List[str]:
        # このメソッドは変更なし (省略)
        if not rule_str or rule_str.strip() in ['－', 'なし', '可変', 'nan']: return []
        clean_rule = rule_str.strip()
        if clean_rule == '自由': return [random.choice(self.all_skills)]
        if clean_rule.startswith('分野:'):
            field_name = clean_rule.split(':')[1].strip()
            if field_name in self.field_skills: return [random.choice(self.field_skills[field_name])]
            return []
        if '+' in clean_rule:
            candidates = [s.strip('《》') for s in clean_rule.split('+') if s.strip('《》') in self.all_skills]
            if not candidates: return []
            return [random.choice(candidates)]
        skills = re.findall(r'《(.*?)》', clean_rule)
        if len(skills) > 1: return [random.choice(skills)]
        elif len(skills) == 1: return skills
        return []

    # --- _acquire_skill, _get_remaining_skill_slots, _is_skill_condition_satisfied は変更なし (省略) ---
    def _acquire_skill(self, npc: NPC, skill_name: str):
        if skill_name and skill_name not in npc.修得特技 and skill_name in self.all_skills:
            npc.修得特技.add(skill_name)
            
            skill_id = self.skill_id_map.get(skill_name)
            if skill_id is not None:
                npc.特技_list.append({
                    'キャラID': npc.連番,
                    '特技ID': skill_id,
                    '特技名': skill_name
                })
                
    def _get_remaining_skill_slots(self, npc: NPC) -> int:
        skill_limit = RANK_SLOTS[npc.階級]['skill']
        return skill_limit - len(npc.修得特技)

    def _is_skill_condition_satisfied(self, npc: NPC, required_rule: str) -> bool:
        clean_rule = required_rule.strip()
        if '分野:' in clean_rule:
            field_name = clean_rule.split(':')[1].strip()
            return any(self.skill_field_map.get(s) == field_name for s in npc.修得特技)
        elif '+' in clean_rule:
            candidates = [s.strip('《》') for s in clean_rule.split('+')]
            return any(s in npc.修得特技 for s in candidates)
        else:
            required_skill = clean_rule.strip('《》')
            return required_skill in npc.修得特技

    # --- 特技決定ロジック本体 ---

    def _determine_skills(self, npc: NPC):
        # --- [準備] 残りスロット計算用の関数を内部で定義 ---
        def get_rem():
            return self._get_remaining_skill_slots(npc)

        # STEP 1: 忍法指定特技の修得
        for ninpo in npc.忍法:
            skill = ninpo.get('指定特技')
            if skill and skill != 'なし' and skill != '任意':
                self._acquire_skill(npc, skill)
        if get_rem() <= 0: return

        # STEP 2: 流派加入必須特技の修得
        school_data = self.master['流派'][self.master['流派']['流派名'] == npc.所属流派]
        required_rule = school_data.iloc[0]['加入必須特技'] if not school_data.empty and '加入必須特技' in school_data.columns and pd.notna(school_data.iloc[0]['加入必須特技']) else 'なし'
        
        if required_rule and required_rule != 'なし':
            is_satisfied = self._is_skill_condition_satisfied(npc, required_rule)
            if not is_satisfied:
                skills_to_acquire = self._parse_skill_acquisition_rule(required_rule)
                if skills_to_acquire: 
                    self._acquire_skill(npc, skills_to_acquire[0])
        if get_rem() <= 0: return

        print(f"DEBUG: キャラ={npc.氏名}, 系列={npc.流派系列}, ターゲット分野={SCHOOL_SERIES_SKILL_MAP.get(npc.流派系列)}")


        # STEP 3: 流派系列の得意分野から「2個」修得
        # ★ 修正ポイント: npc.流派系列 が SCHOOL_SERIES_SKILL_MAP にあるか厳密にチェック
        target_field = SCHOOL_SERIES_SKILL_MAP.get(npc.流派系列)
        
        if target_field:
            # フィールド名（'器術'など）に対応する全特技リストを取得
            field_skills_list = self.field_skills.get(target_field, [])
            # まだ持っていない特技を抽出
            preferred_candidates = [s for s in field_skills_list if s not in npc.修得特技]
            
            if preferred_candidates:
                # 「2個」または「残りスロット」の少ない方を取得数にする
                num_to_take = min(get_rem(), 2)
                chosen = random.sample(preferred_candidates, min(num_to_take, len(preferred_candidates)))
                for s in chosen:
                    self._acquire_skill(npc, s)
        
        if get_rem() <= 0: return

        # STEP 4: 残り枠をランダムな特技で埋める
        rem = get_rem()
        if rem > 0:
            available_skills = [s for s in self.all_skills if s not in npc.修得特技]
            if available_skills:
                chosen_random = random.sample(available_skills, min(rem, len(available_skills)))
                for s in chosen_random:
                    self._acquire_skill(npc, s)
    
    # --- 後処理、奥義、忍具決定ロジック ---
    def _apply_post_processing(self, npc: NPC):
        # このメソッドは変更なし (省略)
        acquired_skill_list = list(npc.修得特技)
        if not acquired_skill_list: return
        sekkin_ninpo = next((n for n in npc.忍法 if n['名前'] == '接近戦攻撃※'), None)
        if sekkin_ninpo:
            final_skill = random.choice(acquired_skill_list)
            sekkin_ninpo['指定特技'] = final_skill
            for n in npc.忍法_list:
                if n['忍法名'] == '接近戦攻撃※':
                    n['指定特技'] = final_skill
                    break

    

    def _determine_ougi(self, npc: NPC):
        # このメソッドは変更なし (省略)
        ougi_count = 1
        if npc.階級 in ['上忍', '上忍頭']: ougi_count = 2
        
        chosen_ougi_names = random.sample(self.ougi_names, ougi_count) 
        
        acquired_skill_list = list(npc.修得特技)
        
        if not acquired_skill_list:
            ougi_skill = 'なし'
        else:
            ougi_skill = random.choice(acquired_skill_list)
            
        for ougi_name in chosen_ougi_names:
            ougi_id = self.ougi_id_map.get(ougi_name)
            
            npc.奥義.append({'名前': ougi_name, '指定特技': ougi_skill})
            
            if ougi_id is not None:
                npc.奥義_list.append({
                    'キャラID': npc.連番,
                    '奥義ID': ougi_id,
                    '奥義名': ougi_name,
                    '指定特技': ougi_skill
                })

    def _determine_ningu(self, npc: NPC):
        # このメソッドは変更なし (省略)
        slots = 2
        for _ in range(slots):
            chosen_ningu = random.choice(self.ningu_names)
            npc.忍具[chosen_ningu] = npc.忍具.get(chosen_ningu, 0) + 1
            
        for ningu_name, count in npc.忍具.items():
            ningu_id = self.ningu_id_map.get(ningu_name)
            if ningu_id is not None:
                npc.忍具_list.append({
                    'キャラID': npc.連番,
                    '忍具ID': ningu_id,
                    '忍具名': ningu_name,
                    '個数': count
                })



    def _check_master_data_consistency(self):
        """
        忍法マスタの指定特技が、特技マスタに存在するかチェックし、警告を出力する。
        """
        ninpo_df = self.all_ninpo_master.copy() # 秘伝を含む全忍法マスタ

        # '指定特技'カラムから特技のルール文字列を抽出
        required_skill_rules = ninpo_df['指定特技'].astype(str).str.strip().unique()
        
        # 自由、分野指定、なし、－などを除外
        rules_to_check = [
            r for r in required_skill_rules 
            if r not in ['自由', 'なし', '－', 'nan'] and not r.startswith('分野:')
        ]

        # 警告を格納するリスト
        warnings = []
        
        for rule_str in rules_to_check:
            # 《》を削除し、'+'で区切られた特技候補を抽出
            # 例: '《針術》《隠蔽術》《異形化》' -> ['針術', '隠蔽術', '異形化']
            # 例: '《分身の術》+《変化の術》' -> ['分身の術', '変化の術']
            
            # 1. 括弧《》で囲まれた特技を全て抽出
            candidates = re.findall(r'《(.*?)》', rule_str)
            # 2. 括弧がない場合は、'+'区切りとして扱う（例: '特技A+特技B'）
            if not candidates and '+' in rule_str:
                 candidates = [s.strip() for s in rule_str.split('+')]
            # 3. どちらでもない場合は、ルール文字列全体を特技名と仮定
            if not candidates:
                 candidates = [rule_str]

            for skill_name in candidates:
                # 特技マスタに存在しないかチェック
                if skill_name not in self.skill_field_map:
                    # その特技名を含む忍法を検索して警告メッセージを作成
                    ninpos_with_error = ninpo_df[
                        ninpo_df['指定特技'].astype(str).str.contains(skill_name.replace('(', r'\(').replace(')', r'\)'))
                    ]['名前'].tolist()

                    warning_msg = (
                        f"特技マスタ未登録名: 「{skill_name}」. "
                        f"使用忍法: {', '.join(ninpos_with_error[:3])}{'他' if len(ninpos_with_error) > 3 else ''}"
                    )
                    if warning_msg not in warnings:
                         warnings.append(warning_msg)


        if warnings:
            print("\n🚨 【マスターデータ整合性 警告】 🚨")
            print("以下の特技名は、特技マスタに存在しません。誤字がないか確認してください。\n")
            for w in warnings:
                print(f" - {w}")
            print("--------------------------------------\n")
        
    def complete_npc_data(self, npc: NPC) -> NPC:
    # --- 1. 流派系列の確定 (検索を強化) ---
    # 空白を削除し、部分一致でも探せるようにする
        target_school = str(npc.所属流派).strip()
    
    # マスターデータから、流派名が含まれている行を探す
        school_data = self.master['流派'][
            self.master['流派']['流派名'].str.contains(target_school, na=False) | 
           (self.master['流派']['流派名'] == target_school)
        ]
    
        if not school_data.empty:
          # 見つかったら最初の1件の系列を採用
             npc.流派系列 = school_data.iloc[0]['流派系列']
        else:
        # それでも見つからない場合、下位流派かもしれないので「系列」という文字で推測するなどの処理
        # もしくは、一旦デバッグで何を探そうとしたか出す
            print(f"⚠️ 警告: 流派 '{target_school}' がマスタに見つかりません")
            npc.流派系列 = '汎用'

    # デバッグ文（Noneじゃないか確認用）
        print(f"DEBUG: マスタにある流派リスト: {self.master['流派']['流派名'].tolist()[:5]}")

        # --- ★ 階級上昇コストの先払い処理 ---
        rank_up_cost = RANK_POINTS.get(npc.階級, 0)
        npc.功績点 -= rank_up_cost

        # --- ★ ここから下が抜けていたため、背景が決まっていませんでした ---
        
        # 2. 背景の決定（ここで npc.背景_list にデータが入ります）
        self._determine_backgrounds(npc)

        # 3. 特技の決定
        self._determine_skills(npc)

        # 4. 忍法の決定
        self._determine_ninpo(npc)

        # 5. 奥義の決定
        self._determine_ougi(npc)

        # 6. 忍具の決定
        self._determine_ningu(npc)

        # 最後に完成したnpcオブジェクトを返す
        return npc
# =======================================================
# 4. 実行関数と実行ブロック
# =======================================================

def run_generation():
    
    # --- 既存キャラクターファイル読み込み ---
    try:
        df_characters = pd.read_excel('キャラクター.xlsx', sheet_name='character')
    except Exception:
        try:
            df_characters = pd.read_csv('キャラクター.csv', encoding='utf_8_sig')
        except Exception as e:
            print(f"既存キャラクターファイルの読み込みエラー: {e}")
            print("ファイル名が「キャラクター.xlsx」（シート名「character」）または「キャラクター.xlsx - character.csv」であることを確認してください。")
            return

    # ★★★ 修正箇所: NaN値の処理と確実な整数型への変換 ★★★
    # 功績点と連番カラムの欠損値(NaN)を0で埋め、整数型(int)に変換します。
    if '功績点' in df_characters.columns:
        df_characters['功績点'] = pd.to_numeric(df_characters['功績点'], errors='coerce').fillna(0).astype(int)
    if '連番' in df_characters.columns:
        df_characters['連番'] = pd.to_numeric(df_characters['連番'], errors='coerce').fillna(0).astype(int)
    # ★★★ 修正箇所: ここまで ★★★

    print(f"--- 既存キャラクター ({len(df_characters)}体) への情報付与開始 ---")

    # データ補完ロジッククラスを初期化
    try:
        generator = NPCGenerator()
    except Exception as e:
        print(f"マスターデータ読み込みエラーにより処理を中断しました: {e}")
        return
    
    # ★★★ 修正箇所: 整合性チェックの実行 ★★★
    generator._check_master_data_consistency() 
    # ★★★ ここまで ★★★
        
    # --- 出力用リスト ---
    all_combined_data: List[Dict[str, Any]] = []
    all_bg_data: List[Dict[str, Any]] = []
    all_ninpo_data: List[Dict[str, Any]] = []
    all_skill_data: List[Dict[str, Any]] = []
    all_ougi_data: List[Dict[str, Any]] = []
    all_ningu_data: List[Dict[str, Any]] = []
    
    # 既存のデータを使ってNPCオブジェクトを初期化し、残りの情報を付与
    for index, row in df_characters.iterrows():
        try:
            # 必要なカラムの値を読み込み、クリーンアップ
            npc_id = row['連番']
            npc_name = str(row.get('名前', f'名無し_{npc_id}')).strip()
            rank_str = str(row.get('階級', '中忍')).strip()
            school_str = str(row.get('下位流派', '汎用')).strip()
            # 功績点と連番は事前にクリーンアップされているため、安全に取得可能
            kouseki_int = int(row.get('功績点', 0)) 
            
            if rank_str not in generator.RANK_SLOTS:
                rank_str = '中忍'

            # NPCオブジェクトを初期化
            npc = NPC(npc_id, npc_name, rank_str, school_str, kouseki_int)
            
            # 決定ロジックを実行
            completed_npc = generator.complete_npc_data(npc)
            
            # 各出力リストにデータを格納
            all_combined_data.append(completed_npc.to_dict())
            all_bg_data.extend(completed_npc.背景_list)
            all_ninpo_data.extend(completed_npc.忍法_list)
            all_skill_data.extend(completed_npc.特技_list)
            all_ougi_data.extend(completed_npc.奥義_list)
            all_ningu_data.extend(completed_npc.忍具_list)
            
        except Exception as e:
            # エラー発生時の連番はすでにintになっているため、.0はつかなくなる
            print(f"致命的なエラー: 連番 {row.get('連番', '不明')} のNPC処理中にエラーが発生しました: {e}")
            
    print(f"情報付与が完了しました。")
    
    # --- 結果のCSV出力 (5つの正規化ファイル + 1つの結合ファイル) ---

    # 1. キャラクタ背景.csv
    df_bg = pd.DataFrame(all_bg_data)
    df_bg = df_bg.rename(columns={'キャラID': '連番'})
    df_bg.to_csv('キャラ背景.csv', index=False, encoding='utf_8_sig')
    
    # 2. キャラクタ忍法.csv
    df_ninpo = pd.DataFrame(all_ninpo_data)
    df_ninpo = df_ninpo.rename(columns={'キャラID': '連番'})
    df_ninpo.to_csv('キャラ忍法.csv', index=False, encoding='utf_8_sig')

    # 3. キャラクタ特技.csv
    df_skill = pd.DataFrame(all_skill_data)
    df_skill = df_skill.rename(columns={'キャラID': '連番'})
    df_skill = df_skill.drop_duplicates(subset=['連番', '特技ID'])
    df_skill.to_csv('キャラ特技.csv', index=False, encoding='utf_8_sig')
    
    # 4. キャラ奥義.csv
    df_ougi = pd.DataFrame(all_ougi_data)
    df_ougi = df_ougi.rename(columns={'キャラID': '連番'})
    df_ougi.to_csv('キャラ奥義.csv', index=False, encoding='utf_8_sig')
    
    # 5. キャラ忍具.csv
    df_ningu = pd.DataFrame(all_ningu_data)
    df_ningu = df_ningu.rename(columns={'キャラID': '連番'})
    df_ningu = df_ningu.drop_duplicates(subset=['連番', '忍具ID'])
    df_ningu.to_csv('キャラ忍具.csv', index=False, encoding='utf_8_sig')

    # 6. 結合ファイル (基本情報と最終功績点)
    df_calculated = pd.DataFrame(all_combined_data)
    
    # 元のデータから古い「功績点」を削除してからマージする
    # これにより、計算後の値（最終功績点）が上書きされるのを防ぎます
    if '功績点' in df_characters.columns:
        df_characters_for_merge = df_characters.drop(columns=['功績点'])
    else:
        df_characters_for_merge = df_characters

    df_output = pd.merge(df_characters_for_merge, df_calculated, on='連番', how='left')
    
    # 名前の重複などを掃除
    df_output = df_output.drop(columns=['氏名_y'], errors='ignore')
    df_output.rename(columns={'氏名_x': '氏名'}, inplace=True)
    
    # ★ ここが重要：HTMLやCSVが「功績点」という名前を期待している場合、
    # 計算後の「最終功績点」を「功績点」という名前に戻して保存します
    df_output['功績点'] = df_output['最終功績点']
    
    df_output.to_csv('generated_npcs_with_base_data.csv', index=False, encoding='utf_8_sig')
    
    print(f"\n--- 完了 ---")
    print(f"以下の**5つの正規化されたファイル**と1つの結合ファイルを出力しました：")
    print(f"- キャラ背景.csv (連番、背景ID、背景名)")
    print(f"- キャラ忍法.csv (連番、忍法ID、忍法名、指定特技)")
    print(f"- キャラ特技.csv (連番、特技ID、特技名)")
    print(f"- キャラ奥義.csv (連番、奥義ID、奥義名、指定特技)")
    print(f"- キャラ忍具.csv (連番、忍具ID、忍具名、個数)")
    print(f"- generated_npcs_with_base_data.csv (元のデータ + 最終功績点)")
    
    if not df_output.empty:
        print("\n--- サンプルNPCの決定データ (抜粋) ---")
        print(df_output[['連番', '氏名', '階級', '功績点', '最終功績点']].head(1).to_markdown(index=False))

if __name__ == '__main__':
    run_generation()