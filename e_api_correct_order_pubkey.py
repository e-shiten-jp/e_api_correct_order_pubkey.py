# -*- coding: utf-8 -*-
# Copyright (c) 2026 Tachibana Securities Co., Ltd. All rights reserved.

# 2021.07.08,   yo.
# 2022.10.25 reviced,   yo.
# 2025.07.27 reviced,   yo.
# 2026.06.20 reviced,   yo
#
# 立花証券ｅ支店ＡＰＩ利用のサンプルコード
#
# 動作確認
# Python 3.13.5 / debian13
# API v4r9
#
# 利用方法: 
# 事前に「e_api_login_pubkey.py」を実行して、仮想URL等を取得しておいてください。
# 実行は「e_api_login_pubkey.py」と同じディレクトリで行ってください。
#
# ------------------------------------------------------------------
#
# APIの基本設計について
# 
# 本APIは、プログラミング初心者や非ITエンジニアの方にも
# 利用しやすいよう、URLにJSON形式のパラメーターを付加して
# 送信する独自方式を採用しています。
# 
# 一般的なWeb APIとは異なる構成ですが、
# HTTPヘッダーやPOSTデータなどの知識を最小限に
# 抑えながら利用できることを重視しています。
# 
# このため、本APIは、URLとJSON文字列を組み立てて
# 送信するだけで利用でき、特別な知識を必要とせず、
# 各種スクリプト言語からも実装しやすいことを
# 優先した設計となっています。
#  
# ------------------------------------------------------------------
#
# 機能: 注文訂正 を行ないます。
#
#
# 訂正・取消での注意点: 
#   訂正・取消も含めＡＰＩでの処理は、非同期処理です。
# 
#   詳しくは、ＡＰＩ　Q＆A
#   Q: ＡＰＩにより返済注文を一旦取消し後、
#       再度発注しようとすると「信用建玉明細にデータがありません」の
#       メッセージが返され発注できません。
#   を参照ください。
#
# == ご注意: ========================================
#   本番環境にに接続した場合、実際に市場に注文が出ます。
#   市場で約定した場合取り消せません。
# ==================================================
#

import urllib3
import datetime
import json
import os
import urllib.parse
from zoneinfo import ZoneInfo

# =========================================================================
# --- 設定項目（定数定義） ---
# =========================================================================
# コマンド用パラメーター -------------------    
S_ORDER_NUMBER = '12345678'     # 注文番号　省略不可 # 注文番号は、注文約定一覧で取得できる。新規注文、応答の該当項目。
S_EIGYOU_DAY = 'yyyymmdd'       # 営業日　省略不可   yyyymmdd    マスター情報の「CLMDateZyouhou」から取得。
S_CONDITION = '*'               # 執行条件  *：変更なし、 0：指定なし、2：寄付、4：引け、6：不成
S_ORDER_PRICE = '*'             # 注文値段  注文値段  *：変更なし、 0：成行に変更、訂正注文値段：指値を変更
S_ORDER_SURYOU = '*'            # 注文数量  注文数量  *：変更なし、訂正数量：数量を変更（増株不可）。
                                # ※訂正数量には、内出来を含んだ数量を指定

# 訂正例 ----------------------
# 値上げ: 100円 -> 110円
# S_ORDER_NUMBER = '12345678'      
# S_EIGYOU_DAY = '20221025'  
# S_CONDITION = '*'
# S_ORDER_PRICE = '110'
# S_ORDER_SURYOU = '*'

# 指値から成行に訂正
# S_ORDER_NUMBER = '12345678'      
# S_EIGYOU_DAY = '20221025'  
# S_CONDITION = '*'
# S_ORDER_PRICE = '0'
# S_ORDER_SURYOU = '*'

# 指値100円から指値100円不出来引け成に訂正
# S_ORDER_NUMBER = '12345678'      
# S_EIGYOU_DAY = '20221025'  
# S_CONDITION = '6'
# S_ORDER_PRICE = '*'
# S_ORDER_SURYOU = '*'

# 株数削減: 500株 -> 200株
# S_ORDER_NUMBER = '12345678'      
# S_EIGYOU_DAY = '20221025'  
# S_CONDITION = '*'
# S_ORDER_PRICE = '*'
# S_ORDER_SURYOU = '200'

# 価格と株数削減を同時に指定
# 値上げ: 100円 -> 110円
# 株数削減: 500株 -> 200株
# S_ORDER_NUMBER = '12345678'      
# S_EIGYOU_DAY = '20221025'  
# S_CONDITION = '*'
# S_ORDER_PRICE = '110'
# S_ORDER_SURYOU = '200'


# --- 共通設定項目 ------------------------------------------------------------
FNAME_URL_INFO = "file_url_info.txt"                # API接続情報ファイル
FNAME_PASSWD2 = "./.auth/file_pwd2.txt"              # 第二パスワード保存ファイル
FNAME_LOGIN_RESPONSE = "./.auth/file_login_response.txt"  # ログイン応答保存先
FNAME_INFO_P_NO = "file_info_p_no.txt"              # p_no保存ファイル

# --- 通信堅牢化のための設定項目 ---
API_TIMEOUT_SECONDS = 15.0  # タイムアウト時間（秒）: 応答がない場合15秒で切り上げる
MAX_RETRY_COUNT = 3         # 最大リトライ回数: 通信エラー時に自動再試行する回数
RETRY_INTERVAL_SECONDS = 5  # リトライ間隔（秒）: 再試行する前に待機する時間
# =========================================================================

# --- 共通ユーティリティ関数 ----------------------------------------------

def func_p_sd_date():
    """
    機能: システム時刻を"p_sd_date"の書式の文字列で返す。
    返値: "p_sd_date"の書式の文字列。 API規定書式 "YYYY.MM.DD-hh:mm:ss.sss"
    引数1: なし
    備考: 
        日本標準時（Japan Standard Time、JST）を利用のこと。
    """
    dt_now = datetime.datetime.now(
        # 日本標準時（Japan Standard Time、JST）を利用
        ZoneInfo("Asia/Tokyo")
    )
    # 年.月.日-時:分:秒 の部分を作成
    str_date = dt_now.strftime("%Y.%m.%d-%H:%M:%S")
    
    # マイクロ秒（6桁ゼロ埋め）から先頭の3桁を切り出してミリ秒を作成
    str_micro = f"{dt_now.microsecond:06d}"
    str_ms = str_micro[0:3]
    
    # ドットで結合してAPI規定書式を完成
    return str_date + "." + str_ms


def func_replace_urlencode(str_input):
    """
    URLエンコードを行う。

    URLでは、スペースや「&」「+」「?」などの記号が
    特別な意味を持つため、そのまま送信できない場合がある。
    そのため、これらの文字を「%xx」形式へ変換する。

    例:
        "A B+C" → "A%20B%2BC"

    本サンプルでは Python標準ライブラリの
    urllib.parse.quote() を利用してURLエンコードを行う。

    他言語へ移植する場合も、自前で変換処理を作成するのではなく、
    各言語が提供する標準のURLエンコード関数を利用することを推奨する。

    主な対応例:
        Python      : urllib.parse.quote()
        Java        : java.net.URLEncoder.encode()
        C#          : Uri.EscapeDataString()
        JavaScript  : encodeURIComponent()
        Go          : url.QueryEscape()

    Parameters
    ----------
    str_input : str
        URLエンコード対象文字列

    Returns
    -------
    str
        URLエンコード後の文字列
    """
    return urllib.parse.quote(str_input, safe='')


def func_read_from_file(str_fname):
    """ファイルから文字情報を一括読み込み（BOMを排除）"""
    str_read = ''
    try:
        # utf-8-sig を指定してBOMを自動的に排除しファイルを開く
        with open(str_fname, 'r', encoding='utf-8-sig') as fin:
            while True:
                line = fin.readline()
                if not line:
                    break
                str_read = str_read + line
        return str_read
    except IOError as e:
        print(f"[エラー] ファイルを読み込めません: {str_fname}")
        raise e


def func_write_to_file(str_fname_output, str_data):
    """ファイルに書き込み、権限を所有者のみ(600)に制限"""
    try:
        # 出力先フォルダの存在を確認し、存在しない場合は自動作成
        str_dir = os.path.dirname(str_fname_output)
        if str_dir and not os.path.exists(str_dir):
            os.makedirs(str_dir, exist_ok=True)

        # データをファイルへ書き込み
        with open(str_fname_output, 'w', encoding='utf-8') as fout:
            fout.write(str_data)
        
        # パーミッションを600（所有者のみ読み書き可能）に制限
        os.chmod(str_fname_output, 0o600)
    except IOError as e:
        print(f"[エラー] ファイルに書き込めません: {str_fname_output}")
        raise e


def func_get_url_info(fname):
    """
    file_url_info.txt からAPI接続設定を取得

    機能: API接続情報をファイルから取得し辞書型で返す
    引数1: 接続先情報を保存したファイル名: fname_url_info

    サポートへの問い合わせは、sJsonOfmt:'5'でお願いします。
    """
    str_url_info = func_read_from_file(fname)
    # JSON形式の文字列を辞書型で取り出す
    return  json.loads(str_url_info)    


def func_get_login_response(str_fname):
    '''
    ログインレスポンスを取得
    '''
    str_login_response = func_read_from_file(str_fname)
    dic_login_response = json.loads(str_login_response)
    return dic_login_response
    

def func_get_p_no(fname):
    """ 
    機能: p_noをファイルから取得する
    引数1: p_noを保存したファイル名（fname_info_p_no = "e_api_info_p_no.txt"）
    """
    str_p_no_info = func_read_from_file(fname)
    # JSON形式の文字列を辞書型で取り出す
    json_p_no_info = json.loads(str_p_no_info)
    int_p_no = int(json_p_no_info.get('p_no'))
    return int_p_no


def func_save_p_no(str_fname_output, int_p_no):
    """p_noを保存するためのJSONファイルを生成"""
    p_no_dict = {"p_no": str(int_p_no)}
    json_data = json.dumps(p_no_dict, indent=4)
    func_write_to_file(str_fname_output, json_data)
    print(f'現在の "p_no" を保存しました。 p_no = {int_p_no} -> {str_fname_output}')


def func_make_url_request_from_dic(
                                    auth_flg,       # ログインFlag。    login:true   login以外:false
                                    url_target,     # 接続先URL
                                    work_dic_req    # API要求項目
):
    '''
    API問合せ用完全URL（クエリパラメータ付）を作成
    
    ------------------------------------------------------------------

    APIの基本設計について

    本APIは、プログラミング初心者や非ITエンジニアの方にも
    利用しやすいよう、URLにJSON形式のパラメーターを付加して
    送信する独自方式を採用しています。

    一般的なWeb APIとは異なる構成ですが、
    HTTPヘッダーやPOSTデータなどの知識を最小限に
    抑えながら利用できることを重視しています。

    このため、本APIは、URLとJSON文字列を組み立てて
    送信するだけで利用でき、特別な知識を必要とせず、
    各種スクリプト言語からも実装しやすいことを
    優先した設計となっています。
    
    ------------------------------------------------------------------
    JSONをHTTPボディではなくURLに付加して送信します。
    詳細はAPIマニュアル参照。
    備考：
        サポートへの問い合わせを考慮し、項目ごとの改行とタブを入れてあります。
    '''
    str_url = url_target
    if auth_flg:
        str_url = urllib.parse.urljoin(str_url, 'auth/')
    json_param = json.dumps(work_dic_req, indent=4, ensure_ascii=False)
    return f"{str_url}?{json_param}"


def func_api_req(str_request_method, str_url): 
    """
    APIリクエストの送信と、Shift-JIS応答のデコード（リトライ・タイムアウト対応版）
    """
    # HTTP通信ライブラリ urllib3 を利用します。
    #
    # requests ライブラリでも同様の処理は可能ですが、
    # 本サンプルでは APIサーバーへの接続処理が分かりやすいよう、
    # より基本的な urllib3 を利用しています。
    #
    # 他言語へ移植する場合も、
    # 「HTTPクライアント生成 → リクエスト送信 → レスポンス受信」
    # の流れを対応するライブラリへ置き換えてください。

    print('--- 送信電文 -------------------------------------------')
    print(str_url)

    # 接続および読み込みのタイムアウト時間を設定
    timeout_config = urllib3.Timeout(connect=API_TIMEOUT_SECONDS, read=API_TIMEOUT_SECONDS)
    http = urllib3.PoolManager()
    
    response_data = None
    status_code = None

    # 最大試行回数に達するまで通信をリトライ
    for attempt in range(1, MAX_RETRY_COUNT + 1):
        try:
            # 2回目以降の試行（再接続）の前に、指定されたインターバル時間待機
            if attempt > 1:
                print(f"[{attempt}/{MAX_RETRY_COUNT} 回目] 再接続を試みます...（{RETRY_INTERVAL_SECONDS}秒待機）")
                time.sleep(RETRY_INTERVAL_SECONDS)

            req = http.request(str_request_method, str_url, timeout=timeout_config)
            status_code = req.status
            response_data = req.data
            break  # 正常に通信できた場合はループを抜ける

        except (TimeoutError, MaxRetryError) as ce:
            print(f"\n[警告] 通信エラーが発生しました (試行: {attempt}/{MAX_RETRY_COUNT})")
            print(f"エラー詳細: {ce}")
            
            # 最大リトライ回数を超えて失敗した場合はConnectionErrorを発生
            if attempt == MAX_RETRY_COUNT:
                raise ConnectionError(
                    f"APIサーバーへの接続に規定回数失敗しました。サーバーがメンテナンス中か、停止している可能性があります。\n"
                    f"設定されたタイムアウト時間: {API_TIMEOUT_SECONDS}秒"
                )
        except Exception as ex:
            print(f"\n[警告] 予期せぬネットワーク例外が発生しました: {ex}")
            if attempt == MAX_RETRY_COUNT:
                raise ex

    print(f"HTTP Status: {status_code}")

    # 受信した電文をShift-JISからUTF-8へデコード（不正なバイトは無視）
    str_response = response_data.decode("shift-jis", errors="ignore")
    print('--- 受信電文 -------------------------------------------')
    print(str_response)
    print('--------------------------------------------------------')

    return str_response


def func_api_request_from_dic(
                                flg_login,          # ログインFlag。    login:true   login以外:false
                                destination_url,    # 接続先URL。
                                                    #    ログイン時は、FNAME_URL_INFOから取得する接続先。
                                                    #   それ以外はログインレスポンスで指定される仮想URL。
                                dic_req_item        # API要求項目
):
    '''
    APIへの問い合わせを実行する。
    '''
    # URL文字列の作成
    str_url = func_make_url_request_from_dic(
                                                flg_login,          # ログインFlag。    login:true   login以外:false
                                                destination_url,    # 接続先URL
                                                dic_req_item        # API要求項目
    )

    # APIへの問い合わせ。
    # リクエストメソッドの指定('GET'、'POST'どちらでも動作します。)
    str_api_response = func_api_req('POST', str_url)

    # apiの返り値（JSON形式の文字列）を辞書型で取り出す
    dic_api_response = json.loads(str_api_response)
    
    return dic_api_response

# --- 共通ユーティリティ関数 ----------------------------------------------






# 参考資料（必ず最新の資料を参照してください。）
#マニュアル
#「立花証券・ｅ支店・ＡＰＩ（v4r2）、REQUEST I/F、機能毎引数項目仕様」
# (api_request_if_clumn_v4r2.pdf)
# p6/46 No.6 CLMKabuCorrectOrder を参照してください。
#
#  6 CLMKabuCorrectOrder
#  1	sCLMID	メッセージＩＤ	char*	I/O	CLMKabuCorrectOrder
#  2	sResultCode	結果コード	char[9]	O	業務処理．エラーコード 0：正常。5桁数字：「結果テキスト」に対応するエラーコード
#  3	sResultText	結果テキスト	char[512]	O	ShiftJis。「結果コード」に対応するテキスト
#  4	sOrderNumber	注文番号	char[8]	I/O	新規注文、応答の該当項目
#  5	sEigyouDay	営業日	char[8]	I/O	営業日（YYYYMMDD）
#  6	sCondition	執行条件	char[1]	I	*：変更なし、 0：指定なし、2：寄付、4：引け、6：不成
#  7	sOrderPrice	注文値段	char[14]    I	*：変更なし、 0：成行に変更、訂正注文値段：指値を変更
#  8	sOrderSuryou	注文数量	char[13]    I	*：変更なし、訂正数量：数量を変更（増株不可）。※訂正数量には、内出来を含んだ数量を指定
#  9	sOrderExpireDay	注文期日	char[8]	    I	*：変更なし、 0：当日、変更注文期日日(YYYYMMDD)[10営業日迄]
# 10	sGyakusasiZyouken   逆指値条件   char[14]	    I	*：変更なし、 0：成行に変更、逆指値注文値段：逆指値注文値段を変更
# 11	sGyakusasiPrice	逆指値注文値段     char[14]    I	*：変更なし、 0：成行に変更、逆指値注文値段：逆指値注文値段を変更
# 12	sSecondPassword	第二パスワード     char[48]    I	第二暗証番号（APIでは省略不可）、''：第二暗証番号省略時、関連資料：「立花証券・ｅ支店・ＡＰＩ、インターフェース概要」の「３－２．ログイン、ログアウト」参照
# 13	sOrderUkewatasiKingaku	注文受渡金額	char[16]	O	注文受渡金額
# 14	sOrderTesuryou	注文手数料	char[16]	O	注文手数料
# 15	sOrderSyouhizei	注文消費税	char[16]	O	注文消費税
# 16	sOrderDate	注文日時	char[14]	O	注文日時（YYYYMMDDHHMMSS）


# ======================================================================================================
#     プログラム始点 
# ======================================================================================================

if __name__ == "__main__":

    # 表示形式を接続情報ファイルから読み込む。
    dic_url_info = func_get_url_info(FNAME_URL_INFO)
    str_sJsonOfmt = dic_url_info.get("sJsonOfmt")

    # 22.第二パスワード
    # APIでは第２暗証番号を省略できない。 関連資料:「立花証券・e支店・API、インターフェース概要」の「3-2.ログイン、ログアウト」参照
    # URLに「#」「+」「/」「:」「=」などの記号を利用した場合エラーとなるため、URLエンコーディングを行う。
    # APIへの入力文字列（特にパスワードで記号を利用している場合）で注意が必要。
    #   '#' →   '%23'
    #   '+' →   '%2B'
    #   '/' →   '%2F'
    #   ':' →   '%3A'
    #   '=' →   '%3D'
    str_sSecondPassword = func_read_from_file(FNAME_PASSWD2).strip()
    str_sSecondPassword = func_replace_urlencode(str_sSecondPassword)        # urlエンコーディング
    
    # ログイン応答を保存した「file_login_response.txt」から、仮想URLと口座情報を取得
    dic_login_property = func_get_login_response(FNAME_LOGIN_RESPONSE)

    # 現在（前回利用した）のp_noをファイルから取得する
    my_p_no = func_get_p_no(FNAME_INFO_P_NO)
    my_p_no = my_p_no + 1
    # 更新した"p_no"を保存する。
    func_save_p_no(FNAME_INFO_P_NO, my_p_no)
    
    print()
    print('-- 注文訂正 ------------------------------')
    # API要求項目のセット
    dic_req_item = {
                        'p_no':             str(my_p_no),
                        'p_sd_date':        func_p_sd_date(),
                        'sCLMID':           'CLMKabuCorrectOrder',  # 注文訂正。
                        'sOrderNumber':     S_ORDER_NUMBER,         # 注文番号　省略不可。注文番号は、注文約定一覧で取得できる。新規注文、応答の該当項目。
                        'sEigyouDay':       S_EIGYOU_DAY,           # 営業日　省略不可   yyyymmdd    マスター情報の「CLMDateZyouhou」から取得。
                        'sCondition':       S_CONDITION,            # 執行条件  *：変更なし、 0：指定なし、2：寄付、4：引け、6：不成
                        'sOrderPrice':      S_ORDER_PRICE,          # 注文値段  注文値段  *：変更なし、 0：成行に変更、訂正注文値段：指値を変更
                        'sOrderSuryou':     S_ORDER_SURYOU,         # 注文数量  注文数量  *：変更なし、訂正数量：数量を変更（増株不可）。
                        'sOrderExpireDay':  '*',                    # 注文期日	*：変更なし、 0：当日、変更注文期日日(YYYYMMDD)[10営業日迄]
                        'sGyakusasiZyouken':'*',                    # 逆指値条件  *：変更なし、 0：成行に変更、逆指値注文値段：逆指値注文値段を変更
                        'sGyakusasiPrice':	'*',                    # 逆指値注文値段  *：変更なし、 0：成行に変更、逆指値注文値段：逆指値注文値段を変更
                        'sSecondPassword':  str_sSecondPassword,     # 22.第二パスワード    APIでは第２暗証番号を省略できない。 関連資料:「立花証券・e支店・API、インターフェース概要」の「3-2.ログイン、ログアウト」参照。
                        'sJsonOfmt':        str_sJsonOfmt            # 表示形式（サポートへの問い合わせでは'5'指定でお願いします。）
    }
    
    # 'CLMKabuCorrectOrder'は、仮想URL:'sUrlRequest'
    str_connection_url = dic_login_property.get('sUrlRequest')
    # API問い合わせ実行
    dic_return = func_api_request_from_dic(
                                                False,                  # ログインFlag。    login:true   login以外:false
                                                str_connection_url,     # 接続先URL。
                                                                        #    ログイン時は、FNAME_URL_INFOから取得する接続先。
                                                                        #   それ以外はログインレスポンスで指定される仮想URL。
                                                dic_req_item            # API要求項目
                                            )

    if dic_return is not None:
        if dic_return.get('p_errno') != '-2' and dic_return.get('p_errno') != '2':
            print('結果コード:\t', dic_return.get('sResultCode'))
            print('結果テキスト:\t', dic_return.get('sResultText'))
            print('注文番号:\t', dic_return.get('sOrderNumber'))
            print('営業日:\t', dic_return.get('sEigyouDay'))
            print('注文受渡金額:\t', dic_return.get('sOrderUkewatasiKingaku'))
            print('注文手数料:\t', dic_return.get('sOrderTesuryou'))
            print('注文消費税:\t', dic_return.get('sOrderSyouhizei'))
            print('注文日時:\t', dic_return.get('sOrderDate'))
            print()
                
        elif dic_return.get('p_errno') == '-2' :
            print()
            print('p_errno', dic_return.get('p_errno'))
            print('p_err', dic_return.get('p_err'))
            print("パラメーターの設定に誤りが有ります。")

        # 仮想URLが無効になっている場合
        # if dic_return.get('p_errno') == '2':
        else:
            print()
            print('p_errno', dic_return.get('p_errno'))
            print('p_err', dic_return.get('p_err'))
            print("仮想URLが有効ではありません。")
            print("e_api_login_pubkey.py")
            print("の実行を再度行い、新しく仮想URL（1日券）を取得してください。")
    else:
        print('API接続自体の失敗')
        print('JSON形式の受信電文ではありません。送信電文、受信電文を確認してください。')         
    
    print()    
    print()
    # 最終の'p_no'を保存する。
    func_save_p_no(FNAME_INFO_P_NO, my_p_no)