import streamlit as st
from supabase import create_client, Client
import pandas as pd
import random

# --- 1. Supabase 연결 설정 ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 2. 데이터베이스 제어 함수 ---
def get_experiment_state():
    response = supabase.table("causality_experiment_state").select("status").eq("id", 1).execute()
    return response.data[0]["status"]

def update_experiment_state(new_status):
    supabase.table("causality_experiment_state").update({"status": new_status}).eq("id", 1).execute()

def get_all_results():
    response = supabase.table("causality_test").select("*").execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert('Asia/Seoul').dt.strftime('%Y-%m-%d %H:%M:%S')
    return df

def reset_experiment_data():
    update_experiment_state("waiting")
    supabase.table("causality_test").delete().neq("student_id", "").execute()

# --- 3. 교수용 대시보드 화면 ---
def professor_view():
    st.title("👨‍🏫 교수용 통제 대시보드")
    
    if 'prof_logged_in' not in st.session_state:
        st.session_state.prof_logged_in = False

    if not st.session_state.prof_logged_in:
        st.info("실험을 통제하려면 교수용 비밀번호를 입력하세요.")
        # [수정 1] 비밀번호(3383) 힌트 제거 및 숨김 처리
        pwd = st.text_input("교수용 비밀번호:", type="password")
        if st.button("로그인"):
            if pwd == "3383":
                st.session_state.prof_logged_in = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
        return

    current_state = get_experiment_state()
    st.success(f"현재 실험 상태: **{current_state.upper()}**")
    
    with st.expander("⚠️ 새 수업 시작 (데이터 초기화)", expanded=False):
        st.warning("이 버튼을 누르면 이전 반의 모든 학생 데이터가 삭제되고 실험이 대기 상태로 초기화됩니다.")
        if st.button("🚨 전체 데이터 삭제 및 새 수업 시작", type="primary"):
            reset_experiment_data()
            st.success("데이터가 초기화되었습니다!")
            st.rerun()
    
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    if col1.button("⏳ 실험 대기"): update_experiment_state("waiting")
    if col2.button("🚀 1단계 시작"): update_experiment_state("stage1")
    if col3.button("⚙️ 2단계 시작"): update_experiment_state("stage2")
    if col4.button("📊 결과 확인"): update_experiment_state("results")
    
    st.divider()
    
    if st.button("🔄 진행 상황 새로고침"):
        df = get_all_results()
        if not df.empty:
            st.subheader("📈 실시간 진행 상황")
            st.write(f"현재 참여 인원: {len(df)}명")
            
            st.markdown("### 📍 1단계 (초기 직관) 정답률")
            stage1_data = df.dropna(subset=['stage1_answer'])
            if not stage1_data.empty:
                correct_total_s1 = len(stage1_data[stage1_data['stage1_answer'] == '허위관계이다'])
                total_s1 = len(stage1_data)
                st.write(f"- **전체 정답자**: {correct_total_s1}/{total_s1} 명 ({(correct_total_s1/total_s1)*100:.1f}%) 정답")
                
                topic_map = {'A': '명품 소비', 'B': '가계부 앱', 'C': '유료 재무상담'}
                for topic_code, topic_name in topic_map.items():
                    topic_data = stage1_data[stage1_data['stage1_topic'] == topic_code]
                    if not topic_data.empty:
                        correct = len(topic_data[topic_data['stage1_answer'] == '허위관계이다'])
                        total = len(topic_data)
                        st.write(f"  * {topic_name} 배정자 중 정답: {correct}/{total} 명")
            
            st.markdown("### 📍 2단계 (측정 수준) 정답률")
            stage2_data = df.dropna(subset=['stage2_measurement', 'stage2_answer'])
            if not stage2_data.empty:
                correct_nominal = len(stage2_data[(stage2_data['stage2_measurement'] == '명목측정') & (stage2_data['stage2_answer'] == '허위관계이다')])
                correct_ratio = len(stage2_data[(stage2_data['stage2_measurement'] == '비율측정') & (stage2_data['stage2_answer'] == '인과관계이다')])
                total2 = len(stage2_data)
                total_correct = correct_nominal + correct_ratio
                
                st.write(f"- **전체 정답자**: {total_correct}/{total2} 명 ({(total_correct/total2)*100:.1f}%) 정답")
                st.write(f"  * 명목측정 선택자 중 정답: {correct_nominal}명")
                st.write(f"  * 비율측정 선택자 중 정답: {correct_ratio}명")
            else:
                st.write("2단계 데이터 제출 전입니다.")
            
            # [수정 3] 교수 화면 데이터프레임에서 'id' 열 숨김 처리
            st.dataframe(df.drop(columns=['id'], errors='ignore'))
        else:
            st.warning("아직 제출된 데이터가 없습니다.")

# --- 4. 학생용 화면 ---
def student_view():
    st.title("📊 데이터 인과성 판독 실험")
    
    if 'student_name' not in st.session_state:
        student_name = st.text_input("이름을 입력하세요:")
        if st.button("시작하기"):
            if student_name:
                st.session_state['student_name'] = student_name
                st.rerun()
        return

    st.write(f"👤 참가자: **{st.session_state['student_name']}**님")
    
    st.info("💡 교수님의 안내가 있으면 아래 새로고침 버튼을 누르세요.")
    if st.button("🔄 화면 새로고침 (다음 단계 확인)", use_container_width=True):
        st.rerun()
        
    st.divider()
    
    current_state = get_experiment_state()
    
    if current_state == "waiting":
        st.warning("⏳ 현재 대기 중입니다. 교수님의 시작 지시가 있으면 새로고침 버튼을 누르세요.")
        
    elif current_state == "stage1":
        if 's1_phase' not in st.session_state:
            st.session_state.s1_phase = 'guess'
            st.session_state.topic = random.choice(['A', 'B', 'C'])
            
        topic = st.session_state.topic

        if st.session_state.s1_phase == 'guess':
            st.subheader("📍 [Step 1] 현상 관찰 및 가설 설정")
            
            if topic == 'A':
                st.info("📉 **데이터 분석 결과**: 명품을 많이 사는 사람(A)이 주식 투자 수익률(B)도 높다는 결과가 나왔습니다.")
            elif topic == 'B':
                st.info("📉 **데이터 분석 결과**: 유료 가계부 앱을 사용하는 사람(A)이 일반인보다 저축액(B)이 월등히 많습니다.")
            elif topic == 'C':
                st.info("📉 **데이터 분석 결과**: 고가의 유료 재무 상담을 받는 사람(A)들이 스스로 투자하는 사람(B)보다 평균 자산 수익률이 15% 높습니다.")
                
            st.warning("이 데이터만 보았을 때, 이것은 원인과 결과(인과관계)일까요, 아니면 단순한 상관관계(허위관계)일까요?")
            
            # [수정 2] index=None을 사용하여 "선택하세요" 옵션 제거
            answer1 = st.radio("당신의 1차 판단은?", ["인과관계이다", "허위관계이다"], index=None)
            if st.button("판단 제출하기"):
                if answer1:
                    response = supabase.table("causality_test").insert({
                        "student_id": st.session_state['student_name'],
                        "stage1_topic": topic,
                        "stage1_answer": answer1
                    }).execute()
                    st.session_state['record_id'] = response.data[0]['id']
                    st.session_state.s1_phase = 'explore'
                    st.rerun()
                else:
                    st.error("답안을 선택해주세요.")

        elif st.session_state.s1_phase == 'explore':
            st.subheader("📍 [Step 2] 제3의 요인 투입 (검증)")
            st.write("방금 내린 판단이 맞는지, 분석 모델에 다양한 **통제변수**를 투입하여 확인해 봅시다.")
            
            variables = ['나이', '성별', '소득 수준', '재무 목표 의식']
            # [수정 2] index=None 및 placeholder 적용
            selected_var = st.selectbox("투입할 통제변수를 선택하세요:", variables, index=None, placeholder="변수를 선택하세요")
            
            if selected_var:
                is_correct = False
                explanation = ""
                
                if topic == 'A' and selected_var == '소득 수준':
                    is_correct = True
                    explanation = "실제 원인은 명품 소비가 아니라, **'소득 수준'**입니다. 소득이 높은 사람은 명품을 살 여유도 있고, 투자 자산 규모가 커서 고급 정보에 접근하거나 장기 투자를 할 확률이 높습니다."
                elif topic == 'B' and selected_var == '재무 목표 의식':
                    is_correct = True
                    explanation = "실제 원인은 앱 자체가 아니라, **'재무 목표 의식'**입니다. 저축하고자 하는 의지가 원래 강한 사람이 유료 앱도 결제하고 저축도 많이 하는 것입니다. 앱은 수단일 뿐 원인이 아닙니다."
                elif topic == 'C' and selected_var == '소득 수준':
                    is_correct = True
                    explanation = "실제 원인은 '재무 상담' 자체가 아니라, 상담을 받을 여유가 있는 **'높은 소득 수준'**입니다. 이 소득 수준이 정보 접근성이나 투자 여력을 높여 수익률을 끌어올린 공통 요인이었습니다."
                
                st.divider()
                if is_correct:
                    # [수정 4] "(그래프가 평평해짐)" 텍스트 삭제
                    st.success(f"📊 **결과 변화**: '{selected_var}'(이)가 비슷한 그룹끼리만 묶어서 다시 비교해 보니, 두 현상 간의 차이가 사라졌습니다!")
                    st.markdown("### 📍 [Step 3] 판독 결과: 허위관계 (Spurious Relationship)")
                    st.info(f"**해설:** {explanation}")
                    
                    if st.button("깨달음을 얻었습니다 (1단계 완료)"):
                        st.session_state.s1_phase = 'done'
                        st.rerun()
                else:
                    st.error(f"📉 **결과 변화**: '{selected_var}'(을)를 기준으로 그룹을 나누어 보았지만, 두 현상 간의 강한 상관관계가 그대로 남아있습니다.")
                    st.write("이 변수는 핵심을 찌르는 제3의 요인이 아닌 것 같습니다. 다른 변수를 선택해 투입해 보세요!")

        elif st.session_state.s1_phase == 'done':
            st.success("✅ 1단계 탐구를 성공적으로 마쳤습니다. 교수님의 2단계 지시가 있을 때까지 대기해주세요.")

    elif current_state == "stage2":
        if 'stage2_done' in st.session_state:
            # [수정 6] "화면 최상단의 새로고침을..." 문구 삭제
            st.success("✅ 2단계 답안 제출이 완료되었습니다. 아래 분석 결과와 해설을 확인하세요.")
            
            # [수정 7] 제출 후 정답 해설 및 타 측정 방식과의 비교 제공
            my_measure = st.session_state.get('my_s2_measure', '')
            my_ans = st.session_state.get('my_s2_ans', '')
            
            st.markdown("### 📊 분석 결과 및 대조 해설")
            if my_measure == "명목측정":
                if my_ans == "허위관계이다":
                    st.success("🎉 **정답입니다!** 단순한 '예/아니오' 식의 **명목측정**은 소득이라는 제3의 요인을 분리해내지 못해 **허위관계**로 나타납니다.")
                else:
                    st.error("❌ **오답입니다.** 단순한 '예/아니오' 식의 **명목측정**은 소득이라는 제3의 요인을 분리해내지 못해 **허위관계**로 나타납니다.")
                st.info("💡 **비교:** 만약 **비율측정**(전체 소득 중 자동이체 비율)을 선택했다면?\n고소득층의 여유 자금 효과에 가려지지 않고, '자동화 시스템' 자체가 저축을 이끄는 순수한 **인과관계**가 뚜렷하게 증명되었을 것입니다.")
            
            elif my_measure == "비율측정":
                if my_ans == "인과관계이다":
                    st.success("🎉 **정답입니다!** **비율측정**을 통해 자동화 강도를 정교하게 측정하면, 소득에 가려지지 않고 넛지(시스템) 자체의 **인과관계**가 증명됩니다.")
                else:
                    st.error("❌ **오답입니다.** **비율측정**을 통해 자동화 강도를 정교하게 측정하면, 소득에 가려지지 않고 넛지(시스템) 자체의 **인과관계**가 증명됩니다.")
                st.info("💡 **비교:** 만약 단순한 **명목측정**(예/아니오)을 선택했다면?\n고소득층의 여유 자금 효과를 분리하지 못해 단순한 **허위관계**로 착각했을 것입니다.")

        else:
            st.subheader("📍 [2단계] 자동이체 시스템과 저축액의 관계")
            
            # [수정 8] 가설을 정확하게 먼저 제시
            st.info("📈 **연구 가설**: 자동이체 저축을 설정한 학생은 그렇지 않은 학생보다 월평균 저축액이 더 많을 것이다.")
            st.write("위 가설을 검증하기 위해 연구자로서 **조작적 정의(측정 방식)**를 결정하고, 그 결과를 예측해 보세요.")
            
            # [수정 5 & 7] 선택 옵션을 동시에 보여주고, '선택하세요' 제거
            measure = st.radio("1. 어떤 측정 방식을 선택하시겠습니까?", 
                               ["A. 명목측정 (자동이체 설정 여부: 예/아니오)", 
                                "B. 비율측정 (전체 소득 대비 자동이체 설정 금액의 비율: %)"], index=None)
            
            ans2 = st.radio("2. 선택한 측정 방식을 사용할 때, '소득 수준(제3의 요인)'을 고려하면 이 관계는 무엇으로 판별될까요?", 
                            ["인과관계이다", "허위관계이다"], index=None)
            
            if st.button("2단계 최종 제출"):
                if measure and ans2:
                    measure_val = "명목측정" if "A" in measure else "비율측정"
                    if 'record_id' in st.session_state:
                        supabase.table("causality_test").update({
                            "stage2_measurement": measure_val,
                            "stage2_answer": ans2
                        }).eq("id", st.session_state['record_id']).execute()
                        
                        # 해설 출력을 위해 세션에 저장
                        st.session_state['stage2_done'] = True
                        st.session_state['my_s2_measure'] = measure_val
                        st.session_state['my_s2_ans'] = ans2
                        st.rerun()
                else:
                    st.error("측정 방식과 판별 결과를 모두 선택해주세요.")

    elif current_state == "results":
        st.success("🎉 모든 실험이 종료되었습니다. 강단 화면에서 우리 반의 종합 통계를 확인하세요.")


# --- 5. 메인 라우팅 (사이드바로 통합) ---
st.sidebar.title("접속 모드 선택")
mode = st.sidebar.radio("원하는 모드를 선택하세요:", ["🧑‍🎓 학생 화면", "👨‍🏫 교수 화면 (관리자)"])

if mode == "👨‍🏫 교수 화면 (관리자)":
    professor_view()
else:
    student_view()
