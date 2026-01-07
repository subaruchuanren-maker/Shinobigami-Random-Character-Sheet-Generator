import pandas as pd
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Any, Set, Union
import os
from pathlib import Path

# =======================================================
# 1. 定数とマスタデータ準備
# =======================================================

FIELD_ORDER = ['器術', '体術', '忍術', '謀術', '戦術', '妖術'] 
FIELD_MAX_SIZE = 11 
OUTPUT_DIR = Path("html")

SCHOOL_SERIES_FIELD_MAP = {
    '斜歯系列': '器術', '鞍馬系列': '体術', 'ハグレ系列': '忍術',
    '比良坂系列': '謀術', '御斎系列': '戦術', '隠忍系列': '妖術',
    '古流': None, '汎用': None, '屍衣': '妖術', 
}

# load_csv_safely 関数は変更なし
def load_csv_safely(filenames: List[str], error_message: str) -> pd.DataFrame:
    for fname in filenames:
        try:
            return pd.read_csv(fname, encoding='utf_8_sig')
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"⚠️ 警告: ファイル '{fname}' は見つかりましたが、読み込み中にエラーが発生しました: {e}")
            continue
    print(f"\n--- エラー: {error_message} ---")
    raise FileNotFoundError(f"必要なファイルが見つかりません。候補: {', '.join(filenames)}")

def load_master_skills(df_skills: pd.DataFrame) -> Dict[str, Dict[str, List[str]]]:
    field_skills_data = df_skills.groupby('分野')['名前'].apply(list).to_dict()
    skill_field_map = df_skills.set_index('名前')['分野'].to_dict()
    return {
        'field_skills_data': field_skills_data,
        'skill_field_map': skill_field_map
    }

def load_master_ninpo(df_ninpo_master: pd.DataFrame) -> Dict[str, str]:
    """忍法マスタから忍法名と流派のマップを作成し、空白を除去する"""
    if '名前' in df_ninpo_master.columns and '流派' in df_ninpo_master.columns:
        df_ninpo_master['名前'] = df_ninpo_master['名前'].astype(str).str.strip()
        return df_ninpo_master.set_index('名前')['流派'].fillna('汎用').to_dict()
    return {}


# 【新規追加】NaNを安全に整数に変換するヘルパー関数
def safe_int_conversion(value: Any, default: int = 0) -> int:
    """NaNまたは非数値であればdefault値を返す"""
    if pd.isna(value) or value is None:
        return default
    try:
        # floatに一度変換することで、'10.0'のような文字列も安全に処理
        return int(float(value))
    except (ValueError, TypeError):
        return default

# load_master_ninpo 関数 (忍法名から流派名を取得)
def load_master_ninpo(df_ninpo_master: pd.DataFrame) -> Dict[str, str]:
    """忍法マスタから忍法名と流派のマップを作成し、空白を除去する"""
    if '名前' in df_ninpo_master.columns and '流派' in df_ninpo_master.columns:
        df_ninpo_master['名前'] = df_ninpo_master['名前'].astype(str).str.strip()
        return df_ninpo_master.set_index('名前')['流派'].fillna('汎用').to_dict()
    return {}

# safe_int_conversion 関数 (NaNエラー対応)
def safe_int_conversion(value: Any, default: int = 0) -> int:
    """NaNまたは非数値であればdefault値を返す"""
    if pd.isna(value) or value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

# =======================================================
# 2. データ変換ロジック
# =======================================================

def get_skill_grid(acquired_skills: Set[str], master_data: Dict[str, Dict[str, List[str]]], school_series: str) -> List[List[Dict[str, Any]]]:
    """
    修得特技セットを6x11のグリッド形式に整形し、特技の間に1つの空欄を挿入して12列構造にする。
    特技の左右の空欄が、特技自身または次の特技が得意分野であれば黒塗りになる。
    """
    
    field_skills = master_data['field_skills_data']
    grid = []
    preferred_field = SCHOOL_SERIES_FIELD_MAP.get(school_series, None)
    
    # 修正: 空欄セルを生成し、直前の分野（field_check）と次の分野（next_field_check）をチェックする
    def conditional_blackout_cell(prev_field: str, next_field: str | None) -> Dict[str, str]:
        """直前の分野 OR 次の分野が得意系列であれば空欄セルを黒塗り（blackout-col）にする"""
        css_classes = 'gap-col' 
        
        # ★ロジック修正: 直前の分野 OR 次の分野が得意系列であれば blackout-col を付与
        if prev_field == preferred_field or next_field == preferred_field:
            css_classes += ' blackout-col'
        
        return {'name': '', 'css': css_classes.strip()} 

    for i in range(FIELD_MAX_SIZE):
        row_final = []
        # 1. 行番号の列 (1列目)
        row_final.append({'name': str(i + 2), 'css': 'row-number'}) 
        
        for field_index, field in enumerate(FIELD_ORDER):
            
            is_preferred_field = field == preferred_field
            skills_in_field = field_skills.get(field, [])
            skill_name = skills_in_field[i] if i < len(skills_in_field) else ''
            cell_css = 'checked' if skill_name in acquired_skills else ''
            
            # A. 特技セル (6個)
            cell_css += ' preferred-field-cell' if is_preferred_field else '' 
            row_final.append({'name': skill_name, 'css': cell_css}) 
            
            # B. 特技の右側の空欄セル (5個)
            # 最後のフィールドの後ろには挿入しない
            if field_index < len(FIELD_ORDER) - 1:
                # 次の分野名を取得
                next_field = FIELD_ORDER[field_index + 1]
                
                # ★修正箇所: 直前の分野(field)と次の分野(next_field)をチェックして空欄セルを生成
                row_final.append(conditional_blackout_cell(field, next_field)) 

        grid.append(row_final)
        
    return grid

def prepare_context(char_row: pd.Series, acquired_data: Dict[str, pd.DataFrame], master_data: Dict[str, Dict[str, List[str]]], df_school: pd.DataFrame, ninpo_school_map: Dict[str, str]) -> Dict[str, Any]:
    """1キャラクター分のデータをHTMLテンプレート用の辞書形式にまとめる"""
    
    char_id = char_row['連番']
    school_name = str(char_row.get('下位流派', char_row.get('流派', '汎用'))).strip() 

    school_data = df_school[df_school['流派名'] == school_name] 
    school_series = school_data.iloc[0]['流派系列'] if not school_data.empty and '流派系列' in school_data.columns else '汎用'

    # 1. 基本情報
    context = {
        'id': char_id,
        'name': str(char_row.get('氏名', '不明')).strip(),
        'style': school_name, 
        'rank': str(char_row.get('階級', '中忍')).strip(),
        'ko': safe_int_conversion(char_row.get('最終功績点', char_row.get('功績点', 0))), 
        'age': safe_int_conversion(char_row.get('年齢', 0)),
        'gender': str(char_row.get('性別', '')).strip(),
    }
    
    # 2. 背景データの処理
    df_bg = acquired_data['背景']
    df_bg_char = df_bg[df_bg['連番'] == char_id]
    bg_detail_list = []
    for _, bg_row in df_bg_char.iterrows():
        bg_detail_list.append({
            '種別': str(bg_row.get('種別', '不明')),
            '背景名': str(bg_row.get('背景名', '不明')),
            '功績点_変動': safe_int_conversion(bg_row.get('功績点_変動', 0))
        })
    context['backgrounds_list'] = bg_detail_list


    # 3. 特技データの処理（グリッド作成）
    df_skill = acquired_data['特技']
    char_skills = set(df_skill[df_skill['連番'] == char_id]['特技名'].tolist())
    # グリッド形式（6x11の12列構造）に変換
    context['skills'] = get_skill_grid(char_skills, master_data, school_series)

    # 4. 忍法データの処理
    df_ninpo = acquired_data['忍法']
    char_ninpo_list = []
    for _, n_row in df_ninpo[df_ninpo['連番'] == char_id].iterrows():
        n_name = n_row['忍法名']
        char_ninpo_list.append({
            'name': n_name,
            'タイプ': chosen_ninpo.get('タイプ', '攻撃'), # 追加
            '間合': chosen_ninpo.get('間合', '-'),      # 追加
            'コスト': chosen_ninpo.get('コスト', '0'),     # 追加
            'skill': n_row.get('指定特技', 'なし'),
            'styles': ninpo_school_map.get(n_name, '汎用')
        })
    context['ninpo'] = char_ninpo_list

    # 奥義リスト作成 (変更なし)
    df_ougi = acquired_data['奥義']
    ougi_list = []
    for _, o_row in df_ougi[df_ougi['連番'] == char_id].iterrows():
        ougi_list.append({
            'name': o_row['奥義名'],
            'skill': o_row.get('指定特技', 'なし')
        })
    context['ougi'] = ougi_list

    # 忍具リスト作成
    df_ningu = acquired_data['忍具']
    items_dict = {}
    for _, i_row in df_ningu[df_ningu['連番'] == char_id].iterrows():
        # ★修正: 忍具の個数に safe_int_conversion を適用
        items_dict[i_row['忍具名']] = safe_int_conversion(i_row['個数'])
    context['items'] = items_dict

    return context

# =======================================================
# 3. メイン実行関数 (変更なし)
# =======================================================

def export_html():
    
    # 1. 必要なCSVファイルと特技マスタの読み込み
    try:
        df_base = load_csv_safely(['generated_npcs_with_base_data.csv'], '基本データファイルが見つかりません。')
        acquired_data = {
            '背景': load_csv_safely(['キャラ背景.csv'], 'キャラ背景.csvが見つかりません。'),
            '忍法': load_csv_safely(['キャラ忍法.csv'], 'キャラ忍法.csvが見つかりません。'),
            '特技': load_csv_safely(['キャラ特技.csv'], 'キャラ特技.csvが見つかりません。'),
            '奥義': load_csv_safely(['キャラ奥義.csv'], 'キャラ奥義.csvが見つかりません。'),
            '忍具': load_csv_safely(['キャラ忍具.csv'], 'キャラ忍具.csvが見つかりません。'),
        }
        df_skills_master = load_csv_safely(
            ['特技.xlsx - 特技_マスタ.csv', '特技_マスタ.csv'], 
            '特技マスタファイルが見つかりません。'
        )
        master_data = load_master_skills(df_skills_master)
        df_school_master = load_csv_safely(
            ['流派.xlsx - 流派_マスタ.csv', '流派_マスタ.csv'], 
            '流派マスタファイルが見つかりません。'
        )
        df_ninpo_master = load_csv_safely(
            ['忍法.xlsx - 忍法_マスタ.csv', '忍法_マスタ.csv'], 
            '忍法マスタファイルが見つかりません。'
        )
        ninpo_school_map = load_master_ninpo(df_ninpo_master)
        
    except FileNotFoundError as e:
        print(f"\n--- 致命的なエラーにより処理を中断しました ---")
        print(e)
        return

    # 2. Jinja2 環境のセットアップ
    file_loader = FileSystemLoader('.') 
    env = Environment(loader=file_loader)
    try:
        template = env.get_template('template.html')
    except Exception:
        print(f"\n--- エラー: 'template.html' が見つかりません。前回の回答で提示した内容で作成してください。 ---")
        return

    # 出力フォルダが存在しない場合は作成
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # 3. HTMLファイルの生成
    html_output_count = 0
    
    for _, row in df_base.iterrows():
        try:
            context = prepare_context(row, acquired_data, master_data, df_school_master, ninpo_school_map)
            
            output_html = template.render(context)
            
            npc_id = row['連番']
            npc_name = str(row.get('氏名', f'名無し_{npc_id}')).strip()
            
            output_filename = OUTPUT_DIR / f"char_sheet_{npc_id}_{npc_name}.html"
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(output_html)
            html_output_count += 1
            
        except Exception as e:
            # エラーの詳細（スタックトレース）を出力しないことで、視認性を高めます
            print(f"HTML生成中にエラーが発生しました: 連番 {row.get('連番', '不明')}, エラー: {type(e).__name__}: {e}")

    print(f"\n--- HTML出力完了 ---")
    print(f"✅ **HTMLファイル ({html_output_count}個)** の出力が完了しました。")
    print(f"ファイルはすべて **{OUTPUT_DIR}/** フォルダ内に保存されました。")


if __name__ == '__main__':
    try:
        import jinja2
    except ImportError:
        print("エラー: HTML出力には Jinja2 ライブラリが必要です。")
        print("コマンドプロンプトで『pip install Jinja2』を実行してインストールしてください。")
    else:
        export_html()