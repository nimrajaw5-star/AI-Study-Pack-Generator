import streamlit as st
from workflow import generate_workflow, markdown_pack, WorkflowError

st.set_page_config(page_title='AI Study Pack Generator', page_icon='📚', layout='wide')
st.title('📚 AI Study Pack Generator')
st.caption('Planning → Content → Assessment → Review → Refinement')

with st.sidebar:
    st.header('Student Profile')
    subject = st.text_input('Subject / Topic', placeholder='e.g. Biomedical Signal Processing')
    level = st.selectbox('Level', ['Beginner', 'Intermediate', 'Advanced'])
    goal = st.selectbox('Goal', ['Exam Preparation', 'Concept Mastery', 'Revision', 'Interview Preparation'])
    minutes = st.number_input('Study Time (minutes)', min_value=15, max_value=1000, value=120, step=15)
    weak = st.text_area('Weak Areas', placeholder='e.g. Fourier transform, filtering')
    style = st.selectbox('Learning Style', ['Balanced', 'Concise', 'Detailed', 'Exam-focused'])
    components = st.multiselect('Include', ['Notes','Cheat Sheet','Flashcards','MCQs','Short Questions','Exam Tips'], default=['Notes','Cheat Sheet','Flashcards','MCQs','Short Questions','Exam Tips'])
    run = st.button('🚀 Generate Study Pack', type='primary', use_container_width=True)

if run:
    if not subject.strip():
        st.error('Please enter a subject or topic.')
    else:
        profile = {'subject': subject.strip(), 'level': level, 'goal': goal, 'study_time_minutes': minutes, 'weak_areas': weak.strip() or 'Not specified', 'learning_style': style, 'requested_components': components}
        try:
            with st.status('Running 5-stage AI workflow...', expanded=True) as status:
                st.write('1/5 Planning')
                context = generate_workflow(profile)
                st.write('2/5 Content generation')
                st.write('3/5 Assessment generation')
                st.write('4/5 Quality review')
                st.write('5/5 Final refinement')
                st.session_state.context = context
                status.update(label='Study pack generated successfully!', state='complete')
        except WorkflowError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f'Unexpected error: {e}')

context = st.session_state.get('context')
if context:
    st.divider()
    st.subheader('🎯 Final Study Pack')
    md = markdown_pack(context)
    st.download_button('⬇️ Download Study Pack', md, 'ai_study_pack.md', 'text/markdown')
    t1,t2,t3,t4,t5 = st.tabs(['Final Pack','Plan','Content','Assessment','Review'])
    with t1: st.markdown(md)
    with t2: st.json(context.plan)
    with t3: st.json(context.content)
    with t4: st.json(context.assessment)
    with t5:
        r = context.review
        cols = st.columns(5)
        for col, key in zip(cols, ['overall_score','coverage_score','accuracy_score','difficulty_score','assessment_score']): col.metric(key.replace('_',' ').title(), r.get(key, 0))
        st.markdown('### Issues')
        for x in r.get('issues', []): st.warning(x)
        st.markdown('### Recommended Fixes')
        for x in r.get('recommended_fixes', []): st.info(x)
else:
    st.info('Enter your details in the sidebar and click Generate Study Pack.')

st.divider()
st.caption('Built with Streamlit + Google Gemini')
