from flask import Flask, render_template_string, request, jsonify, send_from_directory, Response
import os
import json
import random
import time
import urllib.request

app = Flask(__name__)

# EMAIL SETTINGS - HTTPS API (NO SMTP)
# Brevo sends the OTP through its HTTPS API, so Render Free can use it.
app.config['BREVO_API_KEY'] = os.environ.get('BREVO_API_KEY', '')
app.config['BREVO_SENDER_EMAIL'] = os.environ.get('BREVO_SENDER_EMAIL', '')
app.config['BREVO_SENDER_NAME'] = os.environ.get('BREVO_SENDER_NAME', 'X STUDY')

# Dictionary to hold OTP and creation timestamp
otp_store = {}

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#000000">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
    <meta name="apple-mobile-web-app-title" content="X STUDY">
    <link rel="manifest" href="/manifest.webmanifest">
    <link rel="icon" type="image/png" sizes="192x192" href="/xstudy_icon_192.png">
    <link rel="apple-touch-icon" href="/xstudy_icon_192.png">
    <title>X STUDY App</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background-color: #0f172a; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .app-container { width: 100%; max-width: 420px; height: 100vh; background: #ffffff; position: relative; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }

        #splash-screen { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(180deg, #1d4ed8 0%, #1e1b4b 100%); display: flex; flex-direction: column; justify-content: center; align-items: center; z-index: 100; transition: opacity 0.5s ease-out; }
        .splash-logo-card { width: 130px; height: 130px; background: linear-gradient(135deg, #2563eb, #1e1b4b); border-radius: 32px; display: flex; justify-content: center; align-items: center; box-shadow: 0 12px 30px rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.15); }
        .splash-app-name { color: #ffffff; font-size: 28px; font-weight: 800; margin-top: 12px; letter-spacing: 2px; }

        .top-bar { background-color: #000000; color: #ffffff; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }
        .brand-logo-wrap { display: flex; align-items: center; gap: 12px; margin-left: 6px; }
        .brand-text { font-weight: 800; font-size: 21px; color: #ffffff; letter-spacing: 1.5px; }
        .skip-btn { color: #ffffff; font-size: 14px; cursor: pointer; font-weight: 500; }

        .stepper { background-color: #000000; color: #ffffff; padding: 4px 24px 18px 24px; display: flex; justify-content: space-between; align-items: center; position: relative; }
        .step-item { display: flex; flex-direction: column; align-items: center; z-index: 2; }
        .step-circle { width: 22px; height: 22px; border-radius: 50%; border: 1px solid #666666; display: flex; justify-content: center; align-items: center; font-size: 11px; background: #000000; color: #888888; margin-bottom: 4px; }
        .step-circle.active { border-color: #ffffff; color: #ffffff; }
        .step-circle.completed { background: #ffffff; color: #000000; border-color: #ffffff; font-weight: bold; }
        .step-label { font-size: 11px; color: #888888; }
        .step-label.active { color: #ffffff; font-weight: 600; }
        .step-line { position: absolute; top: 15px; left: 45px; right: 45px; height: 1px; background-color: #333333; z-index: 1; }

        .view-screen { display: none; height: 100%; flex-direction: column; background: #ffffff; }
        .content { padding: 20px 16px; overflow-y: auto; flex: 1; }
        .heading { font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 16px; }

        .lang-card { display: flex; align-items: center; justify-content: space-between; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; cursor: pointer; background: #fff; }
        .lang-left { display: flex; align-items: center; gap: 16px; }
        .lang-char { font-size: 19px; font-weight: 700; color: #1e293b; width: 30px; text-align: center; }
        .lang-name { font-size: 15px; font-weight: 500; color: #334155; }

        .input-box-container { position: relative; margin-top: 15px; }
        .input-label { position: absolute; top: -10px; left: 14px; background: #ffffff; padding: 0 6px; font-size: 12px; color: #2563eb; font-weight: 500; }
        .input-field-wrap { display: flex; align-items: center; border: 2px solid #2563eb; border-radius: 8px; padding: 14px; }
        .input-box { border: none; outline: none; font-size: 16px; width: 100%; color: #0f172a; }
        
        .resend-container { display: flex; justify-content: flex-end; align-items: center; margin-top: 12px; font-size: 14px; }
        .resend-btn { color: #94a3b8; font-weight: 700; cursor: not-allowed; text-decoration: none; }
        .resend-btn.active { color: #2563eb; cursor: pointer; }
        .timer-text { color: #64748b; font-size: 13px; margin-left: 8px; }

        .terms-text { margin-top: 30px; font-size: 13px; color: #475569; line-height: 1.6; }
        .terms-text a { color: #2563eb; text-decoration: none; font-weight: 600; }

        .status-badge { display: none; margin-top: 20px; padding: 14px; border-radius: 10px; font-size: 15px; font-weight: 700; text-align: center; }
        .status-success { background: #dcfce7; color: #15803d; border: 2px solid #22c55e; }
        .status-error { background: #fee2e2; color: #b91c1c; border: 2px solid #ef4444; }

        .profile-option { display:flex; align-items:center; gap:12px; padding:13px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:11px; color:#0f172a; cursor:pointer; font-size:14px; }
        .profile-option span:last-child { margin-left:auto; font-size:22px; color:#64748b; }
        .profile-option:hover { background:#f1f5f9; }
        .institute-option { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:14px; border:1px solid #e2e8f0; border-radius:12px; background:#f8fafc; cursor:pointer; font-weight:700; color:#0f172a; }
        .institute-option.active { border:2px solid #2563eb; background:#eff6ff; }
        .bottom-bar { padding: 16px 20px; background: #ffffff; border-top: 1px solid #f1f5f9; }
        .continue-btn { width: 100%; background-color: #cbd5e1; color: #ffffff; border: none; padding: 14px; border-radius: 6px; font-size: 15px; font-weight: 600; cursor: not-allowed; }
        .continue-btn.active { background-color: #2563eb; cursor: pointer; }
    /* Sabhi screens ka scroll top pe lock karne ke liye */
#neet11-screen, #home-screen, #video-screen {
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
}
    
        @keyframes telegramGlow {
            0%,100% { box-shadow: 0 0 0 rgba(14,165,233,0), 0 4px 12px rgba(15,23,42,0.05); transform: translateY(0); }
            50% { box-shadow: 0 0 18px rgba(14,165,233,0.28), 0 7px 18px rgba(15,23,42,0.08); transform: translateY(-1px); }
        }

        /* Small floating actions - only inside the 30-box lecture screen. */
        #xstudy-floating-actions { position:absolute; right:10px; bottom:14px; z-index:120; display:flex; flex-direction:column; align-items:flex-end; gap:9px; pointer-events:none; }
        .xstudy-float { pointer-events:auto; width:46px; height:46px; border-radius:50%; border:1px solid rgba(255,255,255,.95); display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 6px 18px rgba(15,23,42,.20); transition:transform .18s ease, box-shadow .18s ease; position:relative; }
        .xstudy-float:active { transform:scale(.92); }
        .telegram-float { background:#229ED9; color:#fff; font-size:21px; animation:xstudyFloatGlow 2.4s ease-in-out infinite; }
        .ai-float { background:#fff; padding:0; animation:xstudyFloatGlowAI 2.4s ease-in-out infinite; }
        .ai-robot { width:40px; height:40px; border-radius:50%; background:linear-gradient(135deg,#7c3aed,#4f46e5); display:flex; align-items:center; justify-content:center; font-size:21px; }
        .ai-help-bubble { position:absolute; right:38px; top:-2px; white-space:nowrap; background:#111827; color:#fff; padding:5px 8px; border-radius:9px; font-size:10px; font-weight:800; box-shadow:0 5px 12px rgba(15,23,42,.22); }
        .ai-help-bubble::after { content:''; position:absolute; right:-5px; top:9px; border-width:4px 0 4px 6px; border-style:solid; border-color:transparent transparent transparent #111827; }
        @keyframes xstudyFloatGlow { 0%,100%{box-shadow:0 5px 14px rgba(34,158,217,.28)} 50%{box-shadow:0 5px 24px rgba(34,158,217,.58)} }
        @keyframes xstudyFloatGlowAI { 0%,100%{box-shadow:0 5px 14px rgba(99,102,241,.22)} 50%{box-shadow:0 5px 24px rgba(99,102,241,.50)} }

        /* X STUDY in-app Support AI */
        #xstudy-ai-modal { position:fixed; inset:0; z-index:250; background:rgba(15,23,42,.38); display:none; align-items:flex-end; justify-content:center; }
        #xstudy-ai-card { width:min(420px,100%); height:min(600px,86vh); background:#fff; border-radius:22px 22px 0 0; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 -12px 35px rgba(15,23,42,.25); }
        .xstudy-ai-head { padding:13px 15px; display:flex; align-items:center; gap:10px; background:#111827; color:#fff; }
        .xstudy-ai-avatar { width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg,#7c3aed,#4f46e5); display:flex; align-items:center; justify-content:center; font-size:19px; }
        .xstudy-ai-close { margin-left:auto; border:0; background:transparent; color:#fff; font-size:26px; cursor:pointer; }
        #xstudy-ai-messages { flex:1; overflow-y:auto; padding:14px; background:#f8fafc; }
        .xstudy-ai-msg { max-width:84%; padding:10px 12px; border-radius:14px; margin-bottom:10px; font-size:13px; line-height:1.5; white-space:pre-wrap; }
        .xstudy-ai-bot { background:#fff; border:1px solid #e2e8f0; color:#334155; margin-right:auto; }
        .xstudy-ai-user { background:#4f46e5; color:#fff; margin-left:auto; }
        .xstudy-ai-suggestions { display:flex; gap:7px; overflow-x:auto; padding:9px 12px; background:#fff; border-top:1px solid #e2e8f0; }
        .xstudy-ai-chip { white-space:nowrap; border:1px solid #cbd5e1; background:#fff; border-radius:18px; padding:7px 10px; font-size:11px; cursor:pointer; }
        .xstudy-ai-input-row { display:flex; gap:8px; padding:10px 12px; background:#fff; border-top:1px solid #e2e8f0; }
        #xstudy-ai-input { flex:1; min-width:0; border:1px solid #cbd5e1; border-radius:14px; padding:10px 12px; outline:none; font-size:13px; }
        #xstudy-ai-send { width:44px; border:0; border-radius:13px; background:#4f46e5; color:#fff; font-size:18px; cursor:pointer; }
</style>
</head>
"""
HTML_BODY_START = """
<body>
    <div class="app-container">
        <!-- Splash Screen -->
        <div id="splash-screen">
            <div class="splash-logo-card" style="overflow:hidden; background:#000000; border:2px solid rgba(255,255,255,0.35);">
                <img src="data:image/png;base64,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aOGdqKcqWKQAoG/fvh999BFaAEjniXU+nPPly5ePHz9eOJHylUlInA5yB0s/KaWjRo1atGgRMse53e5AICDaBfbv33///fcnJiYa1IbUAaeV1d+pU6cXXnihoKAAeR1Q9KMRkJ2dPXPmzIiICJARfwmJ008KiMiv0+mcMWMGznLCuQKi4I9zvmXLlhtuuB6bhwmR3Z6niehPSEiYNWvWgQMHkEEWnT8U/V6v99133+3RowfIGn8JidMbotG/Y8eOzzzzTH5+viD5CgQC2DXGdG3NqlXXTb82KqpWDQgHglIq9cHJL/dFYyAApKSk3HPPPZs3b0YFbxwrzTn/73//i6w+ICfKSUicOYYhbvX+/ft//PHHFRUVwjCsqanx1Lg550zX16xZM3369NjYWKhLEUsZcZLD2NvRoUOHP/3pTzt27EBZ73a7kTYcf12/fv20adOwFFjUjElISJz+CgAlBdb82Gy24cOHf/rpp5gf9nq97mqPu9rjrvFwzhnjGzZsuOeeezp27CjsRBkgPgnfqWBvBoD09PTHHnts7969ovzX5/O53W5M9uzdu/fee+/F4b2oMGTOX0LiTLQWbTYb2oAAMGrUqG+++QajQD631+vxaprm8/lRiOzdu/evf/1rRkYGflmEkiROBn9OvIsBAwa89NJLyOOG6jwQCIgin6ysrMcee6x9+/b4ZVnnIyEh1QAVBBI2m23cuHGLvvuOM8Y59/t9gYDfmCLOycl58803Bw4caJQ+0ng8gS9O6OMxY8bMnj0buftR9GPDB/569OjRp59+GilAAMBut0s3TkLijLMWrcJafCJiCBERzquv/uOyn37EplBNC2DFiMfjwfrR4sKiTz/+5OKLL3a5XMKWlJqgFV6fULpC9CclJU2bNm3RokWY18XXJLq60Op/7rnnevXqhd8XWRz5siQkJMyw2Wx2uwMA4uLip06dumTJktrSIMawd8xdU+P3+jjnHrd75cqVM2fO7N69u/hzWULectLfGOUHgHPOOeepp57avn27rusY6He73Vjkg6L/4MGDf/3rX6XVLyEh0QhBo6qqw+FwOp2EkKioqDFjxrz77rvIEswYc9e4a6qq3VU1nrpSwuzs7I8//viKK65ISkoyRidkzWizQORp8df27dtfe+21X3/9dVFRkcjxYnkPxvr9fv+qVavuvfdepHOAury9fBcSEhL1KwBBKYp1n/h59+7d//KXv+zcubM2PeD1eWrcaHJibYmu67t27Xr55ZeHDBmCDaVQF1b6/fxCZ0KZivEGhb0vsrvR0dFjxox5++23MzMz8YEjbSdGe9AJcLvdixcvnjhxIvbxgSztb923JiFxGmoC0UIMAG3btr3llluW/7QMo0DILeqvAxqkFRUVy5cvf/TRR88//zwhiVCjSDu03mdusvcjIyPPO++8xx9/fO3atSK24/V6MdQjnvmxY8feeeedkSNH4pvC+i4Z65eQkGhOwYS/uiJcl158yezZXyCrDDaRIbDkHD+srKxes2btk08+MWzYsKioKHE0NGxlPNr0bI2sy3FxcRdeeOFTTz21evVqbNPD2A5S93i9XsHiuX79+scff1zkeEWeQMp9iUaYepxz+SAkGrJWMCihaZqiKL179x43btyECRPOPfdcDPv4/X4AxhjoGqWURrhUAKiqqtqxY8fq1auXL1++efPm4uJiIa1w7WF24Yx6ksirAQDoSOGHiYmJ/fr1u+iii0aNGtWnTx/0n1ChCn2J4xuPHTv2ww8/zJs3b82aNRUVFahWGWNn2mOUkApA4gQILzQz/X4/himGDBkyadKkcePGYc0J5+Bx+znnVGGUEkpVm01FWbZ///5ffvll1apVmzdvPnz4sNfrNQpEbsBpuM3qYJTUERER6enp/fv3v+CCCwYPHpyRkeF0OgEAa3ABQNd1RVFQ7vt8vm3bti1cuHDhwoX79u0TKhkdArmLJZqyMuUjkGisLOOcY+zCKM7S0tKGDRs2fvy4YcOGd+7chRBgjOm6hmsMJZRoPM7Lyztw4MDWrVs3bdq0devWgwcP1tTUGMNE4k8Qp5yZYpT46DOJf4qIiOjUqVO/fv0GDRo0cODAnj174sh1k70vSPzdbvfu3buXLVv2008/bdy4sby8XDwi42ElJKQCkDgxko5SKoRRWlrakCFDxo4bN+T887t27aaqCroLaKjil41kEoWFhZmZmRs3bty4ceOePXuys7MLCwuNp8C8qMk/OHn0gTHdKmI1poBMSkpKampq7969+/fvP2DAgG7duglKBl3XscMOfxVZd5/Pt3v37v/+978//vjj5s2bUe6jq4RRI2nyS0gFIHESaQLM7mJoCADat28/ePDg8ePHX3DBBRkZGSgcdV0XkhGlubHesays7NixY/v27du7d+/27dszMzOzs7NLSkpM0W0RQxcHEQKx5cSiEPSmstSgwff4+Pi0tLT09PS+ffv27du3Z8+e7dq1i4+PF0IfazfxXhhjdrsdj1lZWbljx46VK1f+/PPPmzZtKisrw+9gqAeVqFxsEkZ3XCoAiZMx9CF8gvbt2w8aNGjYsGEDBw7s1atXu3bt8HOMdKPgE/6BCBNxzsvKyo4ePZqdnX3kyJGDBw9mZ2dnZWXl5eWVlZW53e6gFxC07aDeTWLcSCLGhX8o/klka01wuVyxsbHx8fEdO3ZMS0vr2rVrjx49OnXqlJqa2qZNG6HbNE3DI4jLMw7dzcnJ2bx58+rVq9euXbtz587q6mqhUzFJLuW+hPQAJE49nwAMoWqHw9GlS5dBgwaNGTNm4MCBnTp1EhWiaBQLNSBEpJH/gHNeXl5eUlKSn5+flZWVk5OTl5eXl5eXn59fUVFRWVlZWVlZU1MjXJBmvBGHw+FyuaKiouLj42NiYpKTkzt27Ni2bdsOHTp06dIlKSkJdYDQXkaJj/ltq9AvLCw8cODAL7/8sn79+q1bt2ZlZYnvo1sgU7sSUgFInA6aADPGxqrHpKSk3r17n3POOQMHDszIyEAxKoRjIBBgjAnrW3gJgmfCqBWQpqi6urq0tLSsrKy8vLy6urq6urqioqKqqqqiogKHIGqahv8bCAQw7I6iFmNQqqra7Xa73e50OiMjIyMjI6Ojo+Pi4mJjY6OiomJiYmLrEBER4XQ6Ta0MxqiOSQUanYCCgoKDBw9u3br1l19+2bVr1+HDh9HYh7q8rqzmlJAKQOK01QRo4RJCjOIyJiYmNTW1V69eWBuTnp6ekpISExNj/Fs0qIVdjAcRqiVU8McaC0IlJFwNPII4Wr1/rmkaCmhjeb4IFlkpsjGKtW/fvm3btm3ZsmXfvn25ubkej8cYsJJBHgmpAGoFhNwGZ44yQOFrMnsdDkdCQgJmUHv06JGenp6ampqampqYmBgdHW2UrSjKTUlgPJRRNxh9iKYtNnEEcSI8vpVsB72QnJyc7Ozs3bt379u379ChQzk5OcXFxeIGjUIfZDGPhFQAElIZCGVgDBMhnE5n27ZtU1JSunTp0qlTpy5duqSnpycnJ8fFxcXFxblcLiOPgtXeD1o5agyvm2hzhCsQhrwI+bEx3FRYWIjZ6cOHDx8+fDg/Pz8vL8/Y1oBC33RJ8qVLSAUgIRHEKjd1UVlVgt1uj42NjYmJSUhISEhIaNOmTUJCAiqJNm3axMbGRkdHR0VFuVwup9OJ048xc4D1lEHLhJgBgcBvY3A8Hk9VVVV5eXlpaWlxcXF+fn5RUVFpaWlRUVFhYWF5eXllZaVoaTba+FYNJCEhFYCERBNdBGOYPlSylFKKiVyXyxUREeFyuex2u8PhwASvzWZT6mCMPjHGdF1HSjukXRM8+x6Pp6amxufzBW27NSYhhCKR4l5CKgAJiZZVCWAI15hyA81IMGfVPaa+MynuJaQCkJA46dSD6Qdjh0EoCGluShjIRyohISFxyoh+CQkJCQkJCQkJCQlp0UtISEhISFErISEhR7NK/Cb9pQ6QkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkGgsZG+afFASEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhKnE2Shy6n4yuRbk5CQkJBqW0JCrlQJCQmJkwMtPhFMSlXpF0vVLiEhISEhISEhISEhISEhISEhISEhISEhISEhIdEckMnP3/8A5TOUkJCQkBpUQkJCQkJCQkJCWnASEhJSsEhIyMUnISH34CkGKt+lhISEhISEhISEhISEhISEhIREkyGryCXqXSHyIUhISEhISEhISEicAYa8tP0lJCQkpEw8JR+OfFkn2+uQb0RCQkJCQkJC2nfyeUpI21lCvmwJCQmJoJCdwBISEhISEhKt4oTJhyDfo4SEhBQcEhISEhISEhISEhISEhISEhISEhISEhISEhISEmc4ZCuDhIREc0H2AUhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEic0pDddvJ5SkhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISJzCkOWbpzfkPAAJCQkJCQkJCQkJCQkJCQkJCYkzETLyKyEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEh0VyQ/UoSEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhJnLmQlpYSEhMSZif8HjPYKBf5CQpcAAAAASUVORK5CYII=" alt="X STUDY Logo" style="width:100%; height:100%; object-fit:cover; display:block;">
            </div>
            <div class="splash-app-name">X STUDY</div>
        </div>

        <div class="top-bar">
            <div class="brand-logo-wrap">
                <svg width="26" height="26" viewBox="0 0 100 100" fill="none">
                    <path d="M30 70 C 20 50, 40 20, 60 30 C 80 40, 60 70, 40 80 C 20 90, 50 60, 70 40" stroke="#38bdf8" stroke-width="12" stroke-linecap="round"/>
                </svg>
                <span class="brand-text">X STUDY</span>
            </div>
            <div class="skip-btn" onclick="showHomeScreen()">Skip</div>
        </div>
        <div class="stepper">
            <div class="step-line"></div>
            <div class="step-item"><div id="s1-c" class="step-circle active">1</div><div id="s1-l" class="step-label active">Language</div></div>
            <div class="step-item"><div id="s2-c" class="step-circle">2</div><div id="s2-l" class="step-label">Login</div></div>
            <div class="step-item"><div id="s3-c" class="step-circle">3</div><div id="s3-l" class="step-label">Welcome</div></div>
        </div>

        <div id="lang-screen" class="view-screen" style="display: flex;">
            <div class="content">
                <h2 class="heading">Which language do you want to see X STUDY in?</h2>
                <div class="lang-card" onclick="goToLogin('hi')"><div class="lang-left"><span class="lang-char">अ</span><span class="lang-name">हिन्दी</span></div><span>&gt;</span></div>
                <div class="lang-card" onclick="goToLogin('en')"><div class="lang-left"><span class="lang-char">A</span><span class="lang-name">English</span></div><span>&gt;</span></div>
                <div class="lang-card" onclick="goToLogin('bn')"><div class="lang-left"><span class="lang-char">ব</span><span class="lang-name">বাংলা</span></div><span>&gt;</span></div>
                <div class="lang-card" onclick="goToLogin('gu')"><div class="lang-left"><span class="lang-char">ગુ</span><span class="lang-name">ગુજરાતી</span></div><span>&gt;</span></div>
                <div class="lang-card" onclick="goToLogin('mr')"><div class="lang-left"><span class="lang-char">प</span><span class="lang-name">मराठी</span></div><span>&gt;</span></div>
                <div class="lang-card" onclick="goToLogin('ta')"><div class="lang-left"><span class="lang-char">த</span><span class="lang-name">தமிழ்</span></div><span>&gt;</span></div>
            </div>
        </div>
        <div id="onboarding-header" class="header">
    <!-- X STUDY logo, Skip button, etc. -->
</div>

        <div id="login-screen" class="view-screen">
            <div class="content">
                <h2 class="heading" id="login-heading">Login to get started</h2>
                <div class="input-box-container">
                    <span class="input-label" id="field-label">Email ID</span>
                    <div class="input-field-wrap">
                        <input type="email" id="user-input" class="input-box" placeholder="name@example.com" oninput="validateLogin()">
                    </div>
                </div>

                <p class="terms-text" id="terms-desc">
                    By continuing, you confirm that you are above 18 years of age, and you agree to the X STUDY's <a href="#">Terms of Use</a> and <a href="#">Privacy Policy</a>
                </p>
            </div>
            <div class="bottom-bar">
                <button id="login-btn" class="continue-btn" onclick="sendRealOTP()" disabled>Continue</button>
            </div>
        </div>

        <div id="otp-screen" class="view-screen">
            <div class="content">
                <h2 class="heading">Enter Verification Code</h2>
                <p style="color: #64748b; font-size: 14px; margin-bottom: 15px;">Enter the 4-digit verification code sent to your Email Inbox.</p>
                <div class="input-box-container">
                    <span class="input-label">Enter OTP</span>
                    <div class="input-field-wrap"><input type="number" id="otp-input" class="input-box" placeholder="____" oninput="validateOTP()"></div>
                </div>
                
                <div class="resend-container">
                    <span id="resend-btn" class="resend-btn" onclick="triggerResend()">Resend OTP</span>
                    <span id="timer-text" class="timer-text">(30s)</span>
                </div>
                
                <div id="otp-msg" class="status-badge"></div>
            </div>
            <div class="bottom-bar">
                <button id="otp-btn" class="continue-btn" onclick="verifyRealOTP()" disabled>Verify & Continue</button>
            </div>
        </div>
        <!-- BATCH DETAILS SCREEN (Screenshots UI) -->
<div id="batch-details-screen" class="view-screen" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:#ffffff; z-index:85; flex-direction:column;">
    
    <!-- Top Bar with Back Arrow, Title and Header Icons -->
    <div style="display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:1px solid #f1f5f9; background:#ffffff; position:sticky; top:0; z-index:10;">
        <div style="display:flex; align-items:center; gap:10px;">
            <span onclick="closeBatchDetails()" style="font-size:24px; cursor:pointer; font-weight:bold; color:#1e293b; line-height:1;">‹</span>
            <h3 id="selected-batch-title" style="margin:0; font-size:17px; font-weight:800; color:#0f172a;">Arjuna NEET 2027</h3>
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
            <span style="background:#f1f5f9; padding:4px 8px; border-radius:12px; font-size:12px; font-weight:700; color:#475569;">💎 0</span>
            <span style="font-size:18px; cursor:pointer;">💬</span>
            <span style="font-size:18px; cursor:pointer;">🔔</span>
        </div>
    </div>

    <!-- Navigation Tabs (Description, All Classes, Infinity Learning) -->
    <div style="display:flex; justify-content:space-around; align-items:center; border-bottom:1px solid #e2e8f0; background:#ffffff;">
        <div onclick="switchBatchTab('desc', this)" class="batch-tab-item" style="padding:12px 6px; font-size:14px; font-weight:600; color:#64748b; cursor:pointer;">Description</div>
        <div onclick="switchBatchTab('classes', this)" class="batch-tab-item active" style="padding:12px 6px; font-size:14px; font-weight:700; color:#4f46e5; border-bottom:3px solid #4f46e5; cursor:pointer;">All Classes</div>
        <div onclick="switchBatchTab('infinity', this)" class="batch-tab-item" style="padding:12px 6px; font-size:14px; font-weight:600; color:#64748b; cursor:pointer;">👑 Infinity Learning</div>
    </div>

    <!-- Scrollable Content Area -->
    <div style="flex:1; overflow-y:auto; padding:14px 16px 80px 16px; background:#f8fafc;">
        
        <!-- Tab 1: Description Screen -->
        <div id="tab-content-desc" style="display:none; background:#ffffff; padding:16px; border-radius:12px; border:1px solid #e2e8f0;">
            <h4 style="margin-bottom:8px; color:#0f172a;">Batch Overview</h4>
            <p style="font-size:13px; color:#64748b; line-height:1.5;">Welcome to Complete NEET Preparation Batch. Here you will get daily live/recorded lectures, DPPs, and chapter-wise tests.</p>
        </div>

        <!-- Tab 2: All Classes Screen (Subject List Cards) -->
        <div id="tab-content-classes" style="display:flex; flex-direction:column; gap:12px;">
            <!-- Dynamic Content JavaScript se render hoga -->
        </div>

        <!-- Tab 3: Infinity Learning Screen -->
        <div id="tab-content-infinity" style="display:none; background:#ffffff; padding:16px; border-radius:12px; border:1px solid #e2e8f0; text-align:center;">
            <h4 style="color:#4f46e5; margin-bottom:6px;">Infinity Learning Access</h4>
            <p style="font-size:13px; color:#64748b;">Unlock extra revision sessions, doubt engine, and premium test series.</p>
        </div>

    </div>

    <!-- Bottom Sticky Purchase Bar -->
    <div style="position:absolute; bottom:0; left:0; width:100%; background:#ffffff; border-top:1px solid #e2e8f0; padding:10px 16px; display:flex; justify-content:space-between; align-items:center; z-index:20;">
        <div>
            <div style="font-size:18px; font-weight:800; color:#4f46e5;">₹0 <span style="font-size:12px; color:#94a3b8; text-decoration:line-through;">₹0</span></div>
            <div style="font-size:10px; font-weight:800; color:#16a34a; background:#dcfce7; padding:2px 6px; border-radius:4px; display:inline-block;">100% OFF</div>
        </div>
        <button onclick="alert('Proceeding to Buy')" style="background:#4f46e5; color:#ffffff; border:none; padding:12px 28px; border-radius:10px; font-size:15px; font-weight:700; cursor:pointer;">BUY NOW</button>
    </div>

</div>
<!-- SUBJECT CONTENTS SCREEN (GREEN THEME) -->
<div id="video-screen" style="display:none; position:fixed; top:0; left:0; width:100%; height:100vh; background:#f8fafc; z-index:999; flex-direction:column;">
    
    <!-- Top Green Header -->
    <div style="background:#2d6a4f; color:#ffffff; padding:16px 14px; display:flex; align-items:center; gap:14px; width:100%;">
        <span onclick="closeVideoScreen()" style="font-size:24px; cursor:pointer; font-weight:bold; color:#ffffff;">←</span>
        <h3 id="video-batch-title" style="margin:0; font-size:18px; font-weight:700; color:#ffffff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Subject Name</h3>
    </div>

    <!-- Green Navigation Tabs -->
    <div style="background:#2d6a4f; display:flex; justify-content:space-around; align-items:center; padding:10px 0 0 0; border-bottom:3px solid #1b4332; width:100%;">
        <div onclick="switchSubjectTab('lectures', this)" class="sub-tab" style="color:#ffffff; font-weight:700; padding-bottom:8px; border-bottom:3px solid #74c69d; cursor:pointer; font-size:13px;">LECTURES</div>
        <div onclick="switchSubjectTab('notes', this)" class="sub-tab" style="color:#d8f3dc; font-weight:600; padding-bottom:8px; border-bottom:3px solid transparent; cursor:pointer; font-size:13px;">NOTES</div>
        <div onclick="switchSubjectTab('png', this)" class="sub-tab" style="color:#d8f3dc; font-weight:600; padding-bottom:8px; border-bottom:3px solid transparent; cursor:pointer; font-size:13px;">PNG</div>
        <div onclick="switchSubjectTab('dpp', this)" class="sub-tab" style="color:#d8f3dc; font-weight:600; padding-bottom:8px; border-bottom:3px solid transparent; cursor:pointer; font-size:13px;">DPP PDFs</div>
    </div>

    <!-- Content Display Area -->
    <div style="flex:1; overflow-y:auto; padding:16px;">
        
        <!-- Tab 1: Lectures List -->
        <div id="sub-tab-lectures" style="display:flex; flex-direction:column; gap:12px;"></div>

        <!-- Tab 2: Notes List -->
        <div id="sub-tab-notes" style="display:none; flex-direction:column; gap:12px;">
            <div style="background:#ffffff; padding:16px; border-radius:12px; border:1px solid #2d6a4f; color:#2d6a4f; font-weight:600;">📄 Class Notes Available Soon</div>
        </div>

        <!-- Tab 3: PNG List -->
        <div id="sub-tab-png" style="display:none; flex-direction:column; gap:12px;">
            <div style="background:#ffffff; padding:16px; border-radius:12px; border:1px solid #2d6a4f; color:#2d6a4f; font-weight:600;">🖼️ Class PNG Slides Available Soon</div>
        </div>

        <!-- Tab 4: DPP PDFs List -->
        <div id="sub-tab-dpp" style="display:none; flex-direction:column; gap:12px;">
            <div style="background:#ffffff; padding:16px; border-radius:12px; border:1px solid #2d6a4f; color:#2d6a4f; font-weight:600;">📝 DPP PDFs Available Soon</div>
        </div>

    </div>
</div>

        <!-- DASHBOARD HOME SCREEN -->
        <div id="home-screen" class="view-screen">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid #e2e8f0; background: #ffffff; position: sticky; top: 0; z-index: 10;">
                <h3 style="color: #0f172a; font-size: 18px; font-weight: 800;">Dashboard</h3>
                <div onclick="openProfile()" style="width: 38px; height: 38px; background-color: #2563eb; color: #ffffff; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(37,99,235,0.3);">
                    👤
                </div>
            </div>
<div id="lectures-content" class="tab-content">
    <!-- Jab user is par click karega tab dedicated video page khulega -->
    <div class="lecture-card" onclick="openVideoPlayer('Lecture 01: Basics')">
        
    </div>
</div>

            <div class="content" style="padding: 16px; background: #f8fafc; overflow-y: auto;">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px;">
                    <h2 style="color:#0f172a; font-size:18px; font-weight:700; margin:0;">Categories</h2>
                    <button onclick="openInstituteSelector()" style="border:1px solid #2563eb; background:#eff6ff; color:#2563eb; padding:7px 10px; border-radius:9px; font-weight:700; font-size:12px; cursor:pointer;">🏛️ <span id="selected-institute-label">Physics Wallah</span></button>
                </div>
                <div id="institute-choice-note" style="margin:-4px 0 14px; color:#64748b; font-size:12px;">Your app is currently using the selected institute's content.</div>
                
                <div style="display: flex; flex-direction: column; gap: 14px;">
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <img src="https://extended-magenta-gcue9nsg.edgeone.dev/file.png" style="width: 45px; height: 45px; border-radius: 10px; object-fit: contain;">
                            <div>
                                <div style="font-weight: 700; color: #0f172a; font-size: 15px;">Physics Wallah (PW)</div>
                                <div style="font-size: 12px; color: #64748b;">JEE, NEET & Foundation</div>
                            </div>
                        </div>
                        <button onclick="openInstitute('Physics Wallah')" style="background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;">Select</button>
                    </div>

                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <img src="https://i.ibb.co/LXv3mYZZ/careerwill-logo-1.png" style="width: 45px; height: 45px; border-radius: 10px; object-fit: contain;">
                            <div>
                                <div style="font-weight: 700; color: #0f172a; font-size: 15px;">Career Will</div>
                                <div style="font-size: 12px; color: #64748b;">IIT-JEE Coaching</div>
                            </div>
                        </div>
                        <button onclick="openInstitute('Career Will')" style="background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;">Select</button>
                    </div>

                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <img src="https://i.ibb.co/fPgWBXD/Screenshot-20260910-020404.png"  style="width: 45px; height: 45px; border-radius: 10px; object-fit: contain;">
                            <div>
                                <div style="font-weight: 700; color: #0f172a; font-size: 15px;">Khan GS Academy</div>
                                <div style="font-size: 12px; color: #64748b;">UPSC & General Studies</div>
                            </div>
                        </div>
                        <button onclick="openInstitute('Khan GS Academy')" style="background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;">Select</button>
                    </div>

                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <div style="width: 45px; height: 45px; background: #e0e7ff; border-radius: 10px; display: flex; justify-content: center; align-items: center; font-weight: 800; color: #3730a3;">NT</div>
                            <div>
                                <div style="font-weight: 700; color: #0f172a; font-size: 15px;">Next Toppers</div>
                                <div style="font-size: 12px; color: #64748b;">Online Board Preparation</div>
                            </div>
                        </div>
                        <button onclick="openInstitute('Next Toppers')" style="background: #2563eb; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer;">Select</button>
                    </div>

                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 5 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 6 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 7 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 8 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 9 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 10 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 11 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 12 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 13 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 14 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 15 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 16 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 17 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 18 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 19 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                    <div style="background: #ffffff; border-radius: 16px; padding: 16px; display: flex; justify-content: space-between; align-items: center; border: 1px dashed #cbd5e1;"><span style="color: #94a3b8; font-weight: 600;">Course Box 20 (Coming Soon)</span><button style="background: #94a3b8; color: #fff; border: none; padding: 8px 16px; border-radius: 8px; cursor: not-allowed;">Select</button></div>
                </div>
            </div>

        </div>

<!-- NEET 11th BATCH SCREEN -->
<div id="neet11-screen" class="view-screen"
     style="display:none; position:absolute; top:0; left:0;
     width:100%; height:100%; background:#ffffff; z-index:60;
     flex-direction:column;">

    <!-- Header -->
    <div style="display:flex; align-items:center; gap:12px;
         padding:14px 16px; border-bottom:1px solid #e2e8f0;
         background:#ffffff; position:sticky; top:0; z-index:10;">

        <span onclick="closeNEET11()"
              style="font-size:28px; cursor:pointer; line-height:1;">
            ‹
        </span>

        <h3 id="category-screen-title" style="margin:0; font-size:20px; font-weight:800; color:#0f172a;">
            Class:- 11 (NEET)
        </h3>
    </div>

    <!-- Scroll Area -->
    <div style="flex:1; overflow-y:auto; padding:12px 16px 70px 16px;">

        <div id="neet11-batches"></div>

    </div>
</div>
        <!-- BATCHES / LECTURE SCREEN -->
        <div id="lecture-screen" class="view-screen" style="display: none; position: fixed; top:0; left:0; width:100%; height:100%; background: #ffffff; z-index: 100; flex-direction: column;">
            
            <!-- Header Top Bar -->
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid #e2e8f0; background: #ffffff; position: sticky; top:0; z-index: 10;">
                <div style="display: flex; align-items: center; gap: 12px;">
                  <span onclick="openMenuScreen()" style="font-size: 22px; cursor: pointer; font-weight: bold;">☰</span>
  
                    <h3 id="institute-header-title" style="color: #0f172a; font-size: 18px; font-weight: 800; margin: 0;">AS MULTIVERSE</h3>
                </div>
                <!-- YouTube Channel Redirect Link -->
                <a href="https://www.youtube.com/@helptogethercentre" target="_blank" style="text-decoration: none;">
                    <div style="width: 32px; height: 24px; background: #ff0000; border-radius: 6px; display: flex; justify-content: center; align-items: center; color: white; font-size: 12px; font-weight: bold;">▶</div>
                </a>
            </div>

            <!-- Scrollable Content Container -->
            <div style="padding: 12px 16px 70px 16px; overflow-y: auto; flex: 1;">
                <!-- Search Bar Section -->
                <div style="display: flex; gap: 8px; margin-bottom: 16px;">
                    <input type="text" placeholder="Search Here...." style="flex: 1; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none;">
                    <button style="background: #eab308; color: white; border: none; padding: 10px 18px; border-radius: 8px; font-weight: 600; cursor: pointer;">Study</button>
                </div>

                <!-- Live Dynamic Ad Slider Box -->
                <div id="ad-banner-box" style="position: relative; background: linear-gradient(135deg, #25d366, #128c7e); border-radius: 16px; padding: 16px; color: white; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); transition: all 0.5s ease;">
                    <div style="font-size: 12px; font-weight: 700; background: rgba(255,255,255,0.2); display: inline-block; padding: 2px 8px; border-radius: 4px; margin-bottom: 8px;">FEATURED AD</div>
                    <div id="ad-title" style="font-size: 18px; font-weight: 800; margin-bottom: 4px;">Join Our WhatsApp Group</div>
                    <div id="ad-desc" style="font-size: 12px; opacity: 0.9; margin-bottom: 12px;">Get latest updates, PDF notes, and lecture alerts daily!</div>
                    <a id="ad-link" href="https://whatsapp.com" target="_blank" style="background: #ffffff; color: #128c7e; text-decoration: none; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 12px; display: inline-block;">VIEW NOW</a>
                </div>

                <h3 style="color: #ca8a04; font-size: 18px; font-weight: 800; margin-bottom: 12px;">My Batches</h3>

                <!-- Yellow Colored Batches Grid Structure (Total 30 Boxes) -->
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
    <!-- NEET Boxes (3) -->
    <div onclick="openCategoryBatches('NEET 11th')" style="cursor: pointer; border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding-bottom: 8px;">
        <div style="background: #eab308; color: white; padding: 8px; font-weight: bold; font-size: 14px;">NEET</div>
        <div style="font-size: 13px; font-weight: 700; color: #ca8a04; margin-top: 8px;">11th</div>
    </div>
    <div onclick="openCategoryBatches('NEET 12th')" style="cursor: pointer; border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding-bottom: 8px;">
        <div style="background: #eab308; color: white; padding: 8px; font-weight: bold; font-size: 14px;">NEET</div>
        <div style="font-size: 13px; font-weight: 700; color: #ca8a04; margin-top: 8px;">12th</div>
    </div>
    <div onclick="openCategoryBatches('NEET 12th Pass')" style="cursor: pointer; border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding-bottom: 8px;">
        <div style="background: #eab308; color: white; padding: 8px; font-weight: bold; font-size: 14px;">NEET</div>
        <div style="font-size: 13px; font-weight: 700; color: #ca8a04; margin-top: 8px;">12th Pass</div>
    </div>

    <!-- JEE Boxes (3) -->
    <div onclick="openCategoryBatches('JEE 11th')" style="cursor: pointer; border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding-bottom: 8px;">
        <div style="background: #eab308; color: white; padding: 8px; font-weight: bold; font-size: 14px;">JEE</div>
        <div style="font-size: 13px; font-weight: 700; color: #ca8a04; margin-top: 8px;">11th</div>
    </div>
    <div onclick="openCategoryBatches('JEE 12th')" style="cursor: pointer; border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding-bottom: 8px;">
        <div style="background: #eab308; color: white; padding: 8px; font-weight: bold; font-size: 14px;">JEE</div>
        <div style="font-size: 13px; font-weight: 700; color: #ca8a04; margin-top: 8px;">12th</div>
    </div>
    <div onclick="openCategoryBatches('JEE 12th Pass')" style="cursor: pointer; border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding-bottom: 8px;">
        <div style="background: #eab308; color: white; padding: 8px; font-weight: bold; font-size: 14px;">JEE</div>
        <div style="font-size: 13px; font-weight: 700; color: #ca8a04; margin-top: 8px;">12th Pass</div>
    </div>
                    <!-- Remaining Blank Yellow Boxes (24) -->
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 7</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 8</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 9</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 10</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 11</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 12</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 13</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 14</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 15</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 16</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 17</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 18</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 19</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 20</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 21</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 22</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 23</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 24</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 25</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 26</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 27</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 28</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 29</div>
                    </div>
                    <div style="border: 1px solid #fef08a; border-radius: 12px; overflow: hidden; background: #fefce8; text-align: center; padding: 20px 8px;">
                        <div style="background: #eab308; color: white; padding: 6px; font-weight: bold; font-size: 13px; border-radius: 6px;">Box 30</div>
                    </div>
                </div>
            </div>

            <!-- Bottom Navigation Bar -->
            <div style="position: absolute; bottom: 0; left: 0; width: 100%; background: #ffffff; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-around; padding: 8px 0; z-index: 20;">
                <div style="text-align: center; color: #eab308; font-size: 12px; font-weight: bold;">
                    <div>🏠</div>
                    My Batches
                </div>
                <div onclick="openFavourites()" style="text-align: center; color: #64748b; font-size: 12px; cursor: pointer;">
    <div>❤️</div>
    Favourite
</div>
<!-- VIDEO PLAYER SCREEN -->
<div id="video-screen" class="view-screen" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:#ffffff; z-index:90; flex-direction:column;">
    <!-- Header -->
    <div style="display:flex; align-items:center; gap:12px; padding:14px 16px; border-bottom:1px solid #e2e8f0; background:#ffffff; position:sticky; top:0; z-index:10;">
        <span onclick="closeVideoScreen()" style="font-size:28px; cursor:pointer; line-height:1;">‹</span>
        <h3 id="video-batch-title" style="margin:0; font-size:18px; font-weight:800; color:#0f172a;">Batch Video</h3>
    </div>

    <!-- Content & Video Area -->
    <div style="flex:1; overflow-y:auto; padding:16px;">
        <h4 style="margin-bottom:12px; color:#1e293b; font-size:16px;">Lecture 01: Introduction & Basics</h4>
        
        <!-- Video Player Box -->
        <div style="width:100%; aspect-ratio:16/9; background:#000000; border-radius:12px; overflow:hidden; margin-bottom:16px;">
            <iframe id="video-player" width="100%" height="100%" src="https://www.youtube.com/embed/dQw4w9WgXcQ" title="Video Player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
        </div>

        <div style="background:#f8fafc; border:1px solid #e2e8f0; padding:14px; border-radius:10px;">
            <h5 style="color:#0f172a; margin-bottom:4px;">Notes & Resources</h5>
            <p style="color:#64748b; font-size:13px;">Class notes and PDF materials will be uploaded here.</p>
        </div>
    </div>
</div>
         </div>
        </div>

        <!-- PROFILE MODAL -->
<div id="profile-modal" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.55); justify-content:center; align-items:center; z-index:200;">
    <div style="background:#ffffff; padding:20px; border-radius:18px; width:88%; max-width:340px; max-height:88%; overflow-y:auto; box-shadow:0 15px 35px rgba(0,0,0,0.25);">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;">
            <div>
                <h3 style="margin:0 0 4px; color:#0f172a; font-size:20px;">My Profile</h3>
                <p id="profile-email-display" style="color:#64748b; margin:0; font-weight:600; font-size:13px; word-break:break-all;"></p>
            </div>
            <button onclick="closeProfile()" style="border:none; background:#f1f5f9; width:34px; height:34px; border-radius:50%; font-size:20px; cursor:pointer;">×</button>
        </div>

        <div style="display:flex; flex-direction:column; gap:9px;">
            <div onclick="openChangeLog()" class="profile-option"><span>🌙</span><b>ChangeLog</b><span>›</span></div>
            <div onclick="openMyAccount()" class="profile-option"><span>👤</span><b>My Account</b><span>›</span></div>
            <div onclick="openClassOptions()" class="profile-option"><span>🏫</span><b>Class</b><span>›</span></div>
            <div onclick="openTargetOptions()" class="profile-option"><span>🎯</span><b>Target</b><span>›</span></div>
            <div onclick="openInstituteSelector()" class="profile-option"><span>🏛️</span><b>Institute</b><span>›</span></div>
            <div onclick="openFavouritesFromProfile()" class="profile-option"><span>❤️</span><b>Favourite Batches</b><span>›</span></div>
            <div onclick="openExternal('https://discord.com/')" class="profile-option"><span>◉</span><b>Join Discord</b><span>›</span></div>
            <div onclick="openExternal('https://t.me/limistudy')" class="profile-option"><span>✈️</span><b>Join Telegram Channel</b><span>›</span></div>
            <div onclick="openExternal('https://www.instagram.com/')" class="profile-option"><span>◎</span><b>Follow me on Instagram</b><span>›</span></div>
            <div onclick="openExternal('https://whatsapp.com/channel/0029Vb8zzqBK0IBjbxi16t22')" class="profile-option"><span>💬</span><b>Join WhatsApp Channel</b><span>›</span></div>
            <div onclick="openExternal('https://t.me/limistudy')" class="profile-option"><span>📥</span><b>Lecture Downloader Group</b><span>›</span></div>
            <div onclick="openExternal('https://www.youtube.com/@helptogethercentre')" class="profile-option"><span>▶️</span><b>Subscribe on YouTube</b><span>›</span></div>
            <div onclick="logoutUser()" class="profile-option" style="color:#ef4444; border-color:#fecaca; background:#fff7f7;"><span>↪</span><b>Logout</b><span>›</span></div>
        </div>
    </div>

            <!-- SMALL FLOATING ACTIONS: only on the 30-box lecture screen -->
            <div id="xstudy-floating-actions" aria-label="X STUDY quick actions">
                <button class="xstudy-float telegram-float" onclick="openTelegramChannel()" aria-label="Open X STUDY Telegram">✈️</button>
                <button class="xstudy-float ai-float" onclick="openAIDoubtSolver()" aria-label="Open X STUDY AI Help">
                    <span class="ai-help-bubble">AI Help</span>
                    <span class="ai-robot">🤖</span>
                </button>
            </div>
</div>
    <!-- FAVOURITES SCREEN -->
<div id="favourites-screen" class="view-screen" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:#ffffff; z-index:70; flex-direction:column;">
    <div style="display:flex; align-items:center; gap:12px; padding:14px 16px; border-bottom:1px solid #e2e8f0; background:#ffffff; position:sticky; top:0; z-index:10;">
        <span onclick="closeFavourites()" style="font-size:28px; cursor:pointer; line-height:1;">‹</span>
        <h3 style="margin:0; font-size:20px; font-weight:800; color:#0f172a;">My Favourites ❤️</h3>
    </div>
    <div style="flex:1; overflow-y:auto; padding:12px 16px 70px 16px;" id="favourites-container">
        <!-- Liked Batches Yahan Dikhne Lagenge -->
    </div>
</div>
<!-- THREE LINES / MENU SCREEN -->
<div id="menu-screen" class="view-screen" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:#ffffff; z-index:80; flex-direction:column;">
    <div style="display:flex; align-items:center; gap:12px; padding:14px 16px; border-bottom:1px solid #e2e8f0; background:#ffffff;">
        <span onclick="closeMenuScreen()" style="font-size:30px; cursor:pointer; line-height:1;">‹</span>
        <h3 style="margin:0; font-size:20px; font-weight:800; color:#0f172a;">Menu</h3>
    </div>
    <div style="flex:1; padding:20px; display:flex; flex-direction:column; gap:12px; overflow-y:auto;">
        <div onclick="openInstituteSelector()" class="profile-option"><span>🏛️</span><b>INSTITUTE</b><span>›</span></div>
        <div onclick="openFavouritesFromMenu()" class="profile-option"><span>❤️</span><b>FAVOURITES</b><span>›</span></div>
        <div onclick="openChangeLog()" class="profile-option"><span>🌙</span><b>CHANGELOG</b><span>›</span></div>
        <div onclick="openExternal('https://discord.com/')" class="profile-option"><span>◉</span><b>JOIN DISCORD</b><span>›</span></div>
        <div onclick="openExternal('https://t.me/limistudy')" class="profile-option"><span>✈️</span><b>JOIN TELEGRAM CHANNEL</b><span>›</span></div>
        <div onclick="openExternal('https://www.instagram.com/')" class="profile-option"><span>◎</span><b>INSTAGRAM</b><span>›</span></div>
        <div onclick="openExternal('https://whatsapp.com/channel/0029Vb8zzqBK0IBjbxi16t22')" class="profile-option"><span>💬</span><b>WHATSAPP CHANNEL</b><span>›</span></div>
        <div onclick="openExternal('https://www.youtube.com/@helptogethercentre')" class="profile-option"><span>▶️</span><b>YOUTUBE</b><span>›</span></div>
        <div onclick="logoutUser()" class="profile-option" style="color:#ef4444; border-color:#fecaca; background:#fff7f7;"><span>↪</span><b>LOGOUT</b><span>›</span></div>
    </div>
</div>

<!-- INSTITUTE SELECTOR -->
<div id="institute-modal" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.55); justify-content:center; align-items:center; z-index:210;">
    <div style="background:#fff; width:88%; max-width:340px; max-height:88%; overflow-y:auto; border-radius:18px; padding:20px; box-shadow:0 15px 35px rgba(0,0,0,0.25);">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;">
            <div><h3 style="margin:0 0 4px; color:#0f172a;">Choose Institute</h3><p style="margin:0; color:#64748b; font-size:12px;">Current: <b id="current-institute-modal">Physics Wallah</b></p></div>
            <button onclick="closeInstituteSelector()" style="border:none; background:#f1f5f9; width:34px; height:34px; border-radius:50%; font-size:20px; cursor:pointer;">×</button>
        </div>
        <div id="institute-options" style="display:flex; flex-direction:column; gap:10px;"></div>
    </div>
</div>

<!-- CHANGELOG MODAL -->
<div id="changelog-modal" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.55); justify-content:center; align-items:center; z-index:215;">
    <div style="background:#fff; width:88%; max-width:340px; border-radius:18px; padding:20px; box-shadow:0 15px 35px rgba(0,0,0,0.25);">
        <h3 style="margin:0 0 12px; color:#0f172a;">ChangeLog</h3>
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:14px; color:#475569; font-size:13px; line-height:1.7;">
            <b>New:</b> X STUDY branding & logo<br>
            <b>New:</b> Persistent login until logout<br>
            <b>New:</b> Institute switching from Menu/Profile<br>
            <b>New:</b> Functional Telegram, WhatsApp, Instagram, Discord & YouTube buttons<br>
            <b>Fixed:</b> Back navigation to the category boxes<br>
            <b>Safe:</b> Existing institute/category/batch structure preserved
        </div>
        <button onclick="closeChangeLog()" style="margin-top:14px; width:100%; background:#2563eb; color:#fff; border:none; padding:12px; border-radius:10px; font-weight:700; cursor:pointer;">Close</button>
    </div>
</div>
    </div>
"""
HTML_BODY_END = """

<!-- X STUDY IN-APP SUPPORT AI MODAL -->
<div id="xstudy-ai-modal" onclick="if(event.target===this) closeAIDoubtSolver()">
  <div id="xstudy-ai-card">
    <div class="xstudy-ai-head">
      <div class="xstudy-ai-avatar">🤖</div>
      <div><div style="font-weight:800;font-size:15px;">X STUDY AI Help</div><div style="font-size:10px;opacity:.75;">App Support • Doubt Assistant</div></div>
      <button class="xstudy-ai-close" onclick="closeAIDoubtSolver()">×</button>
    </div>
    <div id="xstudy-ai-messages"></div>
    <div class="xstudy-ai-suggestions">
      <button class="xstudy-ai-chip" onclick="sendXStudyAIMessage('Naya batch kaise add karu?')">Batch Add</button>
      <button class="xstudy-ai-chip" onclick="sendXStudyAIMessage('All Classes kaise add karu?')">All Classes</button>
      <button class="xstudy-ai-chip" onclick="sendXStudyAIMessage('Institute kaise change karu?')">Institute</button>
      <button class="xstudy-ai-chip" onclick="sendXStudyAIMessage('Login/logout kaise kaam karta hai?')">Login Help</button>
    </div>
    <div class="xstudy-ai-input-row">
      <input id="xstudy-ai-input" type="text" placeholder="Apna X STUDY doubt likhiye..." onkeydown="if(event.key==='Enter') sendXStudyAIMessage()">
      <button id="xstudy-ai-send" onclick="sendXStudyAIMessage()">➤</button>
    </div>
  </div>
</div>
    <script>
    // ================= SAFE APP STORAGE =================
    // Agar browser/WebView localStorage ko temporarily block kare, app loading par nahi atkega.
    const xStorage = {
        getItem(key) {
            try { return window.localStorage.getItem(key); } catch (e) { return null; }
        },
        setItem(key, value) {
            try { window.localStorage.setItem(key, value); } catch (e) {}
        },
        removeItem(key) {
            try { window.localStorage.removeItem(key); } catch (e) {}
        }
    };

    let currentInstitute = xStorage.getItem('xstudySelectedInstitute') || "Physics Wallah";
    let currentCategory = xStorage.getItem('xstudySelectedCategory') || "NEET 11th";
    let currentUser = xStorage.getItem('xstudyLoggedInEmail') || '';
    // Institute selection persists until the user logs out.
    let hasSelectedInstitute = xStorage.getItem('xstudyInstituteSelected') === '1';
    let menuReturnScreen = 'lecture-screen';
    let selectedLang = 'en';
    let timerInterval = null;
    let timeLeft = 30;

    function hideSplashScreen() {
        const splash = document.getElementById('splash-screen');
        if (!splash || splash.dataset.hidden === '1') return;

        splash.dataset.hidden = '1';

        // Logged-in users ko onboarding/login screen ka flash nahi dikhana.
        if (currentUser) {
            enterLoggedInApp();
        }

        splash.style.opacity = '0';
        setTimeout(() => {
            splash.style.display = 'none';
        }, 450);
    }

    // Splash ko DOMContentLoaded par bhi aur safety fallback se bhi hide karo.
    window.addEventListener('DOMContentLoaded', () => {
        updateSelectedInstituteUI();
        setTimeout(hideSplashScreen, 1200);
    });

    // Agar kisi WebView/browser mein DOMContentLoaded unusual delay kare,
    // tab bhi loading screen permanently visible nahi rahegi.
    setTimeout(hideSplashScreen, 2200);


        // ================= X STUDY APP STATE =================
        function hideOnboarding() {
            const topBar = document.querySelector('.top-bar');
            const stepper = document.querySelector('.stepper');
            const header = document.getElementById('onboarding-header') || document.querySelector('.header');
            if (topBar) topBar.style.display = 'none';
            if (stepper) stepper.style.display = 'none';
            if (header) header.style.display = 'none';
        }

        function enterLoggedInApp() {
            hideOnboarding();
            ['lang-screen','login-screen','otp-screen','neet11-screen','batch-details-screen','video-screen','menu-screen','favourites-screen','profile-modal','institute-modal','changelog-modal'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.style.display = 'none';
            });
            const home = document.getElementById('home-screen');
            if (home) home.style.display = 'flex';
            updateSelectedInstituteUI();
        }

        function updateSelectedInstituteUI() {
            const label = document.getElementById('selected-institute-label');
            if (label) label.innerText = currentInstitute;
            const modalLabel = document.getElementById('current-institute-modal');
            if (modalLabel) modalLabel.innerText = currentInstitute;
            const header = document.getElementById('institute-header-title');
            if (header) header.innerText = currentInstitute + ' Lectures';
        }

        function openExternal(url) {
            if (!url) return;
            window.open(url, '_blank');
        }

        function closeProfile() {
            const p = document.getElementById('profile-modal');
            if (p) p.style.display = 'none';
        }

        function openMyAccount() {
            alert('Logged in as: ' + (currentUser || 'User') + '\\nInstitute: ' + currentInstitute);
        }

        function openClassOptions() {
            closeProfile();
            document.getElementById('home-screen').style.display = 'flex';
            alert('Class categories are available on the home screen. Tap any category box to open its batches.');
        }

        function openTargetOptions() {
            alert('Target settings: NEET / JEE categories are available on the home screen.');
        }

        function openFavouritesFromProfile() {
            closeProfile();
            openFavourites();
        }

        function openFavouritesFromMenu() {
            closeMenuScreen();
            openFavourites();
        }

        function openChangeLog() {
            closeProfile();
            closeMenuScreen();
            document.getElementById('changelog-modal').style.display = 'flex';
        }

        function closeChangeLog() {
            document.getElementById('changelog-modal').style.display = 'none';
        }

        function openInstituteSelector() {
            closeProfile();
            const menu = document.getElementById('menu-screen');
            if (menu) menu.style.display = 'none';
            renderInstituteOptions();
            document.getElementById('institute-modal').style.display = 'flex';
        }

        function closeInstituteSelector() {
            document.getElementById('institute-modal').style.display = 'none';
        }

        function renderInstituteOptions() {
            const box = document.getElementById('institute-options');
            if (!box) return;
            const institutes = ['Physics Wallah','Career Will','Khan GS Academy','Vibrant Academy','Next Toppers'];
            box.innerHTML = '';
            institutes.forEach(name => {
                const active = name === currentInstitute ? ' active' : '';
                box.innerHTML += `<div class="institute-option${active}" onclick="changeInstitute('${name.replace(/'/g, "\\'")}')"><span>🏛️ ${name}</span><span>${active ? '✓' : '›'}</span></div>`;
            });
        }

        function changeInstitute(name) {
            currentInstitute = name;
            xStorage.setItem('xstudySelectedInstitute', name);
            xStorage.setItem('xstudyInstituteSelected', '1');
            hasSelectedInstitute = true;
            updateSelectedInstituteUI();
            closeInstituteSelector();
            // Go to the boxes/category screen so the new institute immediately controls what opens.
            document.getElementById('home-screen').style.display = 'none';
            document.getElementById('menu-screen').style.display = 'none';
            document.getElementById('neet11-screen').style.display = 'none';
            document.getElementById('batch-details-screen').style.display = 'none';
            document.getElementById('video-screen').style.display = 'none';
            document.getElementById('favourites-screen').style.display = 'none';
            document.getElementById('lecture-screen').style.display = 'flex';
            document.getElementById('institute-header-title').innerText = name + ' Lectures';
            alert('Institute changed to ' + name + '. Ab app isi institute ke according chalega.');
        }

        function logoutUser() {
            if (!confirm('Logout from X STUDY?')) return;
            xStorage.removeItem('xstudyLoggedInEmail');
            xStorage.removeItem('xstudySelectedInstitute');
            xStorage.removeItem('xstudyInstituteSelected');
            xStorage.removeItem('xstudySelectedCategory');
            currentUser = '';
            hasSelectedInstitute = false;
            currentInstitute = 'Physics Wallah';
            closeProfile();
            document.getElementById('menu-screen').style.display = 'none';
            location.reload();
        }

        const i18n = {
            en: { title: "Login to get started", email: "Email ID", continue: "Continue", terms: 'By continuing, you confirm that you are above 18 years of age, and you agree to the X STUDY <a href="#">Terms of Use</a> and <a href="#">Privacy Policy</a>' },
            hi: { title: "शुरू करने के लिए लॉगिन करें", email: "ईमेल आईडी", continue: "जारी रखें", terms: 'आगे बढ़कर, आप यह पुष्टि करते हैं कि आपकी आयु 18 वर्ष से अधिक है, और आप X STUDY की <a href="#">उपयोग की शर्तों</a> और <a href="#">गोपनीयता नीति</a> से सहमत हैं' }
        };

        function goToLogin(lang) {
            selectedLang = i18n[lang] ? lang : 'en';
            applyTranslations();
            document.getElementById('lang-screen').style.display = 'none';
            document.getElementById('login-screen').style.display = 'flex';
            document.getElementById('s1-c').className = "step-circle completed"; document.getElementById('s1-c').innerText = "✓";
            document.getElementById('s2-c').className = "step-circle active"; document.getElementById('s2-l').className = "step-label active";
        }

        function applyTranslations() {
            const t = i18n[selectedLang] || i18n['en'];
            document.getElementById('login-heading').innerText = t.title;
            document.getElementById('field-label').innerText = t.email;
            document.getElementById('login-btn').innerText = t.continue;
            document.getElementById('terms-desc').innerHTML = t.terms;
        }

        function validateLogin() {
            const val = document.getElementById('user-input').value.trim();
            const btn = document.getElementById('login-btn');
            const isValidEmail = val.includes('@') && val.includes('.');
            btn.className = isValidEmail ? "continue-btn active" : "continue-btn";
            btn.disabled = !isValidEmail;
        }

        function startResendTimer() {
            clearInterval(timerInterval);
            timeLeft = 30;
            const resendBtn = document.getElementById('resend-btn');
            const timerSpan = document.getElementById('timer-text');
            
            resendBtn.className = "resend-btn";
            timerSpan.innerText = `(${timeLeft}s)`;

            timerInterval = setInterval(() => {
                timeLeft--;
                if (timeLeft > 0) {
                    timerSpan.innerText = `(${timeLeft}s)`;
                } else {
                    clearInterval(timerInterval);
                    timerSpan.innerText = "";
                    resendBtn.className = "resend-btn active";
                }
            }, 1000);
        }

        function triggerResend() {
            if (timeLeft <= 0) {
                // Clear old input box and error message on resend
                document.getElementById('otp-input').value = "";
                document.getElementById('otp-msg').style.display = 'none';
                validateOTP();
                sendRealOTP();
            }
        }

        function sendRealOTP() {
            const emailInput = document.getElementById('user-input').value.trim();
            if (emailInput) {
                currentUser = emailInput;
            }

            const btn = document.getElementById('login-btn');
            btn.innerText = "Sending...";
            btn.disabled = true;

            fetch('/api/send-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier: currentUser })
            }).then(res => res.json()).then(data => {
                btn.innerText = "Continue";
                btn.disabled = false;
                if (data.success) {
                    showOTPScreen();
                    startResendTimer();
                } else {
                    alert("OTP Error: " + data.message);
                }
            }).catch(err => {
                btn.innerText = "Continue";
                btn.disabled = false;
                alert("Server Connection Error");
            });
        }

        function showOTPScreen() {
            document.getElementById('login-screen').style.display = 'none';
            document.getElementById('otp-screen').style.display = 'flex';
            document.getElementById('s2-c').className = "step-circle completed"; document.getElementById('s2-c').innerText = "✓";
            document.getElementById('s3-c').className = "step-circle active"; document.getElementById('s3-l').className = "step-label active";
        }

        function validateOTP() {
            const val = document.getElementById('otp-input').value.trim();
            const btn = document.getElementById('otp-btn');
            btn.className = (val.length >= 4) ? "continue-btn active" : "continue-btn";
            btn.disabled = (val.length < 4);
        }
           function verifyRealOTP() {
            const code = document.getElementById('otp-input').value.trim();
            const msg = document.getElementById('otp-msg');
            
            fetch('/api/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier: currentUser, otp: code })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    xStorage.setItem('xstudyLoggedInEmail', currentUser); // Login ko persistent rakho
                    // Verification success hone wale block mein add karein:
document.querySelector('.top-bar').style.display = 'none';
document.querySelector('.stepper').style.display = 'none';
// Onboarding Header Ko Hide Karein
const onboardingHeader = document.querySelector('.header') || document.getElementById('onboarding-header');
if (onboardingHeader) {
    onboardingHeader.style.display = 'none'
}                    msg.className = "status-badge status-success"; 
                    msg.innerText = " Verified Successfully!"; 
                    msg.style.display = "block";
                    document.getElementById('otp-btn').style.display = "none";
                    clearInterval(timerInterval);

                    // Stepper complete kar do
                    document.getElementById('s3-c').className = "step-circle completed"; 
                    document.getElementById('s3-c').innerText = "✓";

                    // Verified hone ke 1 sec baad naya white screen dikhayega
                    setTimeout(() => {
                        document.getElementById('otp-screen').style.display = 'none';
                        document.getElementById('home-screen').style.display = 'flex';
                    }, 1000);

                } else {
                    msg.className = "status-badge status-error"; 
                    msg.innerText = "✕ " + data.message; 
                    msg.style.display = "block";
                }
            });
        }
        function openProfile() {
            document.getElementById('profile-email-display').innerText = currentUser || 'User';
            document.getElementById('profile-modal').style.display = 'flex';
        }

        function closeDetailScreen() {
    // Detail screen chhupao
    document.getElementById('detail-screen').style.display = 'none';
    
    // Home screen vapas dikhao
    document.getElementById('home-screen').style.display = 'block';
}  
function showHomeScreen() {
    // Top onboarding header ko hide karein
    const header = document.getElementById('onboarding-header') || document.querySelector('.header');
    if (header) {
        header.style.display = 'none';
    }

    // Aapka baki purana showHomeScreen ka code...
    document.getElementById('home-screen').style.display = 'flex';
}    
// 1. Har Institute Ke Lectures Ka Data
        const instituteData = {
            "Physics Wallah": [
                { title: "Lecture 01: Physics Basics", duration: "45 mins" },
                { title: "Lecture 02: Vectors & Motion", duration: "50 mins" },
                { title: "Lecture 03: Newton's Laws", duration: "1 hour" }
            ],
            "Vibrant Academy": [
                { title: "Lecture 01: Organic Chemistry Intro", duration: "40 mins" },
                { title: "Lecture 02: Chemical Bonding", duration: "55 mins" }
            ],
            "Khan GS Academy": [
                { title: "Lecture 01: Indian History Overview", duration: "1 hour 10 mins" },
                { title: "Lecture 02: Geography & Maps", duration: "50 mins" }
            ],
            "Next Toppers": [
                { title: "Lecture 01: Maths Class 10 Trigonometry", duration: "35 mins" }
            ]
        };

        // 2. Open Button Click Par Naya Page Khologe
        function openInstitute(name) {
           currentInstitute = name;
           xStorage.setItem('xstudySelectedInstitute', name);
           updateSelectedInstituteUI();
             // Home screen chhupao
            document.getElementById('home-screen').style.display = 'none';
            document.getElementById('neet11-screen').style.display = 'none';
            document.getElementById('batch-details-screen').style.display = 'none';
            document.getElementById('video-screen').style.display = 'none';
            // Lecture screen dikhao
            document.getElementById('lecture-screen').style.display = 'flex';

            // Header Name Set Karo
            document.getElementById('institute-header-title').innerText = name + " Lectures";
   
            // Lectures List Clear Karo
            const container = document.getElementById('lectures-container');
            container.innerHTML = "";

            // Dynamic Lectures Load Karo
            const lectures = instituteData[name] || [
                { title: "Lecture 01: Demo Class", duration: "30 mins" },
                { title: "Lecture 02: Practice Sheet", duration: "25 mins" }
            ];

            lectures.forEach(item => {
                container.innerHTML += `
                    <div style="background: #ffffff; border: 1px solid #e2e8f0; padding: 14px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
                        <div>
                            <div style="font-weight: 700; color: #0f172a; font-size: 14px;">${item.title}</div>
                            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Duration: ${item.duration}</div>
                        </div>
                        <button onclick="alert('Play Lecture: ${item.title}')" style="background: #16a34a; color: #fff; border: none; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px; cursor: pointer;">▶ Play</button>
                    </div>
                `;
            });
        }
const instituteBatchesData = {
    // ================================================================
    // BATCH DATA FORMAT
    // Har batch ke andar aap apni marzi se:
    // title, image, description, classes aur infinity add kar sakte ho.
    // Isi structure ko copy karke unlimited batches add kiye ja sakte hain.
    // ================================================================
    "NEET 11th": {
        "Physics Wallah": [
            {
                title: "Arjuna NEET 2.0 2027",
                image: "https://img.sanishtech.com/u/ec094d8d833a8c4e9ac083c02a94cb7a.png",
                description: "Arjuna NEET 2.0 2027 — Class 11 NEET preparation with complete Physics, Chemistry and Biology coverage, DPPs and tests.",
                classes: [
                    { name: "Notices", chapters: "17 Chapters", icon: "📢", bg: "#eff6ff" },
                    { name: "Physics by Saleem Sir", chapters: "33 Chapters", icon: "⚙️", bg: "#fef2f2" },
                    { name: "Physics by Neeraj Kumar Chau...", chapters: "27 Chapters", icon: "🏫", bg: "#eff6ff" },
                    { name: "Botany By Vipin Sharma Sir", chapters: "23 Chapters", icon: "🧪", bg: "#fdf2f8" },
                    { name: "Botany By Dr. Akanksha Agar...", chapters: "20 Chapters", icon: "🌱", bg: "#eff6ff" },
                    { name: "Zoology By Samapti Sinha Ma'...", chapters: "24 Chapters", icon: "🔬", bg: "#fdf2f8" },
                    { name: "Zoology By Sujeet Tripathi", chapters: "18 Chapters", icon: "🧬", bg: "#fdf2f8" },
                    { name: "Physical Chemistry By Manoj K...", chapters: "16 Chapters", icon: "⚛️", bg: "#eff6ff" },
                    { name: "Organic Chemistry By Pankaj S...", chapters: "10 Chapters", icon: "🌿", bg: "#fdf2f8" },
                    { name: "Organic Chemistry By Shubh K...", chapters: "9 Chapters", icon: "🌱", bg: "#fdf2f8" },
                    { name: "Inorganic Chemistry By Manoj ...", chapters: "13 Chapters", icon: "🧪", bg: "#eff6ff" },
                    { name: "Inorganic Chemistry By Kunwa...", chapters: "14 Chapters", icon: "⚗️", bg: "#fdf2f8" },
                    { name: "Physics By Rajwant Singh Sir (...", chapters: "17 Chapters", icon: "📐", bg: "#eff6ff" }
                ],
                infinity: ["Revision Sessions", "Doubt Support", "Premium Test Series"]
            },
            {
                title: "Arjuna NEET 2027",
                image: "https://d2bp2kg43v62.cloudfront.net/batch/Arjuna_NEET_2027.png",
                description: "Arjuna NEET 2027 — Complete Class 11 NEET course with subject-wise classes, practice and tests.",
                classes: [
                    { name: "Physics", chapters: "Complete Class 11", icon: "⚡", bg: "#eff6ff" },
                    { name: "Physical Chemistry", chapters: "Complete Class 11", icon: "⚛️", bg: "#fef2f2" },
                    { name: "Organic Chemistry", chapters: "Complete Class 11", icon: "🧪", bg: "#fdf2f8" },
                    { name: "Inorganic Chemistry", chapters: "Complete Class 11", icon: "⚗️", bg: "#eff6ff" },
                    { name: "Botany", chapters: "Complete Class 11", icon: "🌱", bg: "#fdf2f8" },
                    { name: "Zoology", chapters: "Complete Class 11", icon: "🧬", bg: "#eff6ff" },
                    { name: "DPP & Tests", chapters: "Practice + Tests", icon: "📝", bg: "#fefce8" }
                ],
                infinity: ["Fast Revision", "Doubt Sessions", "Mock Tests"]
            }
        ],
        "Career Will": [
            {
                title: "Nurture 2.0 (Class 11th) Online NEET 2028", image: "data:image/jpeg;base64,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", badge: "NEW", badgeColor: "#16a34a", subtitle: "Kota's Top HOD Team", startDate: "10-Jun-2026",
                description: "Nurture 2.0 (Class 11th) Online NEET 2028 — complete Class 11 NEET preparation with subject-wise lectures, notes, DPPs and tests.",
                classes: [
                    { name: "Today Class", classCount: 0, notes: 0, icon: "T", bg: "#eff6ff" },
                    { name: "Intro", classCount: 2, notes: 4, icon: "I", bg: "#eff6ff" },
                    { name: "Test Paper", classCount: 0, notes: 10, icon: "T", bg: "#eff6ff" },
                    { name: "Modules", classCount: 0, notes: 13, icon: "M", bg: "#eff6ff" },
                    { name: "Physics", classCount: 116, notes: 106, icon: "P", bg: "#eff6ff" },
                    { name: "Physical Chemistry", classCount: 82, notes: 82, icon: "P", bg: "#eff6ff" },
                    { name: "Organic Chemistry", classCount: 7, notes: 7, icon: "O", bg: "#eff6ff" }
                ], infinity: ["Revision Sessions", "Doubt Support", "NEET Test Series"]
            }
        ],
        "Khan GS Academy": [
            {
                title: "Khan Sir NEET Special 2027",
                image: "https://via.placeholder.com/300x170?text=Khan+Sir+NEET",
                description: "Khan Sir NEET Special 2027 — Dedicated NEET preparation content for Class 11 students.",
                classes: [
                    { name: "Physics", chapters: "Class 11", icon: "⚡", bg: "#eff6ff" },
                    { name: "Chemistry", chapters: "Class 11", icon: "🧪", bg: "#fef2f2" },
                    { name: "Biology", chapters: "Class 11", icon: "🌱", bg: "#fdf2f8" },
                    { name: "Practice Tests", chapters: "NEET Pattern", icon: "📝", bg: "#fefce8" }
                ],
                infinity: ["Revision", "Doubt Classes", "NEET Test Series"]
            }
        ]
    },

    "NEET 12th": {
        "Physics Wallah": [
            {
                title: "LAKSHYA NEET 2027",
                image: "https://i.ibb.co/whS9QPkB/lakshya-neet-2027.png",
                status: "Ongoing | started on 26th March' 26",
                description: "Lakshya NEET 2027 — Class 12 NEET preparation with complete syllabus coverage and exam-focused practice.",
                classes: [
                    { name: "Physics by Mr Sir", chapters: "35 Chapters", icon: "⚡", bg: "#eff6ff" }
                ],
                infinity: ["Board + NEET Revision", "Doubt Engine", "Full Syllabus Tests"]
            }
        ],
        "Career Will": [
            {
                title: "Enthuse 2.0 (Class 12th) Online NEET 2027", image: "data:image/jpeg;base64,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", badge: "LIVE", badgeColor: "#ef233c", subtitle: "Kota's Top HOD Team", startDate: "10-Jun-2026",
                description: "Enthuse 2.0 (Class 12th) Online NEET 2027 — complete Class 12 NEET preparation with subject-wise lectures, notes, DPPs and tests.",
                classes: [
                    { name: "Today Class", classCount: 4, notes: 0, icon: "T", bg: "#eff6ff" },
                    { name: "Intro", classCount: 2, notes: 4, icon: "I", bg: "#eff6ff" },
                    { name: "Test Paper", classCount: 0, notes: 10, icon: "T", bg: "#eff6ff" },
                    { name: "Modules", classCount: 0, notes: 24, icon: "M", bg: "#eff6ff" },
                    { name: "Physics", classCount: 97, notes: 97, icon: "P", bg: "#eff6ff" },
                    { name: "Physical Chemistry", classCount: 63, notes: 63, icon: "P", bg: "#eff6ff" },
                    { name: "Organic Chemistry", classCount: 52, notes: 52, icon: "O", bg: "#eff6ff" },
                    { name: "Inorganic Chemistry", classCount: 46, notes: 46, icon: "I", bg: "#eff6ff" },
                    { name: "Botany", classCount: 20, notes: 21, icon: "B", bg: "#eff6ff" },
                    { name: "Zoology", classCount: 66, notes: 72, icon: "Z", bg: "#eff6ff" }
                ], infinity: ["Revision Classes", "Doubt Support", "Full Tests"]
            }
        ]
    },

    "NEET 12th Pass": {
        "Physics Wallah": [
            {
                title: "Yakeen NEET 2027",
                image: "https://via.placeholder.com/300x170?text=Yakeen+NEET",
                description: "Yakeen NEET 2027 — Dropper-focused NEET preparation with complete syllabus revision and intensive testing.",
                classes: [
                    { name: "Physics", chapters: "Complete NEET Syllabus", icon: "⚡", bg: "#eff6ff" },
                    { name: "Chemistry", chapters: "Complete NEET Syllabus", icon: "🧪", bg: "#fef2f2" },
                    { name: "Botany", chapters: "Complete NEET Syllabus", icon: "🌱", bg: "#fdf2f8" },
                    { name: "Zoology", chapters: "Complete NEET Syllabus", icon: "🧬", bg: "#eff6ff" },
                    { name: "Test Series", chapters: "NEET Pattern", icon: "📝", bg: "#fefce8" }
                ],
                infinity: ["Dropper Revision", "Doubt Engine", "NEET Mock Tests"]
            }
        ],
        "Career Will": [
            {
                title: "Achiever (Dropper) Online NEET 2027", image: "data:image/jpeg;base64,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", badge: "LIVE", badgeColor: "#ef233c", subtitle: "Kota's Top HOD Team", startDate: "06-Jul-2026",
                description: "Achiever (Dropper) Online NEET 2027 — repeaters ke liye focused NEET preparation, revision, practice and tests.",
                classes: [
                    { name: "Today Class", classCount: 3, notes: 0, icon: "T", bg: "#eff6ff" }, { name: "Intro", classCount: 3, notes: 4, icon: "I", bg: "#eff6ff" },
                    { name: "Test Paper", classCount: 0, notes: 7, icon: "T", bg: "#eff6ff" }, { name: "Modules", classCount: 0, notes: 45, icon: "M", bg: "#eff6ff" },
                    { name: "Physics - 11th", classCount: 8, notes: 8, icon: "P", bg: "#eff6ff" }, { name: "Physics - 12th", classCount: 41, notes: 41, icon: "P", bg: "#eff6ff" },
                    { name: "Physical Chemistry", classCount: 0, notes: 0, icon: "P", bg: "#eff6ff" }, { name: "Inorganic Chemistry", classCount: 34, notes: 34, icon: "I", bg: "#eff6ff", live: true },
                    { name: "Organic Chemistry", classCount: 52, notes: 52, icon: "O", bg: "#eff6ff" }, { name: "Zoology", classCount: 0, notes: 0, icon: "Z", bg: "#eff6ff" },
                    { name: "Botany", classCount: 48, notes: 47, icon: "B", bg: "#eff6ff" }, { name: "Physics - 11th (VOD)", classCount: 131, notes: 136, icon: "P", bg: "#eff6ff" },
                    { name: "Physics - 12th (VOD)", classCount: 132, notes: 131, icon: "P", bg: "#eff6ff" }, { name: "Physical Chemistry (VOD)", classCount: 111, notes: 109, icon: "P", bg: "#eff6ff" },
                    { name: "Organic Chemistry (VOD)", classCount: 92, notes: 97, icon: "O", bg: "#eff6ff" }, { name: "Zoology (VOD)", classCount: 70, notes: 69, icon: "Z", bg: "#eff6ff" },
                    { name: "Botany (VOD)", classCount: 129, notes: 128, icon: "B", bg: "#eff6ff" }
                ], infinity: ["Rapid Revision", "Doubt Classes", "Grand Tests"]
            }
        ]
    },

    // ==================== JEE ====================
    // Future JEE batches isi format mein add karein.
    "JEE 11th": {},
    "JEE 12th": {},
    "JEE 12th Pass": {}
};

// Current institute + current category ke batches nikaalne ka single function.
function getCurrentBatches() {
    const instituteData = instituteBatchesData[currentCategory] || {};
    return instituteData[currentInstitute] || [];
}

function renderNEET11Batches() {
    const container = document.getElementById('neet11-batches');
    if (!container) return;

    const favourites = JSON.parse(xStorage.getItem('limiFavouriteBatches') || '[]');
    const activeBatches = getCurrentBatches();

    container.innerHTML = "";

    // IMPORTANT: koi fake Batch 1 / Batch 2 generate nahi hoga.
    if (!activeBatches.length) {
        container.innerHTML = `
            <div style="text-align:center; padding:40px 20px; color:#64748b; font-weight:600;">
                Is institute ke liye <b>${currentCategory}</b> mein abhi koi batch add nahi kiya gaya hai.
            </div>
        `;
        return;
    }

    activeBatches.forEach((batch, index) => {
        const isFavourite = favourites.some(item =>
            item.title === batch.title &&
            (item.institute || currentInstitute) === currentInstitute &&
            (item.category || currentCategory) === currentCategory
        );
        const safeTitle = String(batch.title || 'Batch').replace(/'/g, "\'");
        const badge = batch.badge || '';
        const badgeColor = batch.badgeColor || '#16a34a';
        container.innerHTML += `
            <div onclick="openBatch('${safeTitle}')" style="background:#ffffff; border-bottom:1px solid #e5e7eb; padding:14px 10px; cursor:pointer;">
                <div style="display:flex; align-items:center; gap:14px;">
                    <div style="width:132px; height:88px; border-radius:50%; overflow:hidden; background:#f1f5f9; flex-shrink:0; display:flex; align-items:center; justify-content:center;">
                        <img src="${batch.image || 'https://via.placeholder.com/300x170?text=Batch'}" onerror="this.src='https://via.placeholder.com/300x170?text=Batch';" style="width:100%; height:100%; object-fit:cover; display:block;">
                    </div>
                    <div style="min-width:0; flex:1;">
                        <div style="display:flex; align-items:center; gap:6px;">
                            <div style="font-size:17px; font-weight:700; color:#171717; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${batch.title}</div>
                            ${badge ? `<span style="margin-left:auto; background:${badgeColor}; color:#fff; padding:7px 10px; border-radius:4px; font-size:12px; font-weight:800; flex-shrink:0;">${badge}</span>` : ''}
                        </div>
                        <div style="font-size:14px; color:#8a8a8a; margin-top:8px;">${batch.subtitle || "Kota's Top HOD Team"}</div>
                        <div style="font-size:13px; color:#8a8a8a; margin-top:8px;">📅 Start Date: ${batch.startDate || '—'}</div>
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end; margin-top:10px;">
                    <button onclick="event.stopPropagation(); toggleFavourite(${index})" style="border:1px solid #e5e7eb; background:#fff; border-radius:50%; width:34px; height:34px; font-size:18px; cursor:pointer;">${isFavourite ? '❤️' : '🤍'}</button>
                </div>
                <button onclick="event.stopPropagation(); openBatch('${safeTitle}')" style="width:100%; margin-top:8px; background:#5b45e8; color:white; border:none; padding:12px; border-radius:9px; font-size:15px; font-weight:700; cursor:pointer;">Let's Study</button>
            </div>
        `;
    });
}

// Line 784/795 ke niche yahan paste karein:

function openFavourites() {
    document.getElementById('lecture-screen').style.display = 'none';
    document.getElementById('home-screen').style.display = 'none';
    document.getElementById('favourites-screen').style.display = 'flex';
    renderFavourites();
}

function closeFavourites() {
    document.getElementById('favourites-screen').style.display = 'none';
    document.getElementById('home-screen').style.display = 'flex';
}

function renderFavourites() {
    const container = document.getElementById('favourites-container');
    const favourites = JSON.parse(xStorage.getItem('limiFavouriteBatches') || '[]');

    if (favourites.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:40px; color:#64748b;">No favourite batches added yet!</div>`;
        return;
    }

    container.innerHTML = "";
    favourites.forEach((batch) => {
        container.innerHTML += `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:12px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                <div style="position:relative; width:100%; aspect-ratio:16/9; overflow:hidden; border-radius:12px; background:#f1f5f9;">
                    <img src="${batch.image}" onerror="this.src='https://static.pw.live/5eb393ee95fab7468a79d189/d949b2c3-488b-49ef-8a50-bf69022e39e5.png';" style="width:100%; height:100%; object-fit:cover;">
                </div>
                <div style="font-size:18px; font-weight:800; color:#171717; padding:14px 2px 12px;">${batch.title}</div>
            </div>
        `;
    });
}
// 1. Subject & Teacher list Data
// Default list sirf compatibility/fallback ke liye hai.
// Real batch ke liye data ab instituteBatchesData ke classes field se aata hai.
const batchSubjectsList = [
    { name: "Notices", chapters: "17 Chapters", icon: "📢", bg: "#eff6ff" },
    { name: "Physics", chapters: "Complete Course", icon: "⚡", bg: "#eff6ff" },
    { name: "Chemistry", chapters: "Complete Course", icon: "🧪", bg: "#fef2f2" },
    { name: "Biology", chapters: "Complete Course", icon: "🌱", bg: "#fdf2f8" }
];

const sampleLecturesData = [
    { title: "Class-01 | Units & Measurements Part-01", date: "Today", duration: "1:56:53", youtubeUrl: "https://youtu.be/i-oYWhVpp5M" },
    { title: "Class-02 | Units & Measurements Part-02", date: "Yesterday", duration: "01:15:00", youtubeUrl: "https://youtu.be/i-oYWhVpp5M" },
    { title: "Class-03 | Motion in a Straight Line", date: "2 days ago", duration: "01:28:40", youtubeUrl: "https://youtu.be/i-oYWhVpp5M" }
];

let currentBatchDetails = null;
let currentSubjectDetails = null;

function getCurrentBatchDetails(batchTitle) {
    const batches = getCurrentBatches();
    return batches.find(batch => batch.title === batchTitle) || null;
}

function renderBatchDescription(details) {
    const box = document.getElementById('tab-content-desc');
    if (!box) return;
    const text = (details && details.description) ? details.description : 'Is batch ki description abhi add nahi ki gayi hai. instituteBatchesData mein description: "..." add karein.';
    box.innerHTML = `<h4 style="margin-bottom:8px; color:#0f172a;">Batch Overview</h4><p style="font-size:13px; color:#64748b; line-height:1.6; margin:0;">${text}</p>`;
}

function renderInfinityLearning(details) {
    const box = document.getElementById('tab-content-infinity');
    if (!box) return;
    const items = (details && Array.isArray(details.infinity)) ? details.infinity : [];
    box.innerHTML = `
        <h4 style="color:#4f46e5; margin-bottom:10px;">Infinity Learning Access</h4>
        ${items.length ? items.map(item => `<div style="padding:10px 12px; margin:7px 0; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; color:#475569; font-size:13px; font-weight:600; text-align:left;">👑 ${item}</div>`).join('') : '<p style="font-size:13px; color:#64748b;">Is batch ke liye Infinity Learning content abhi add nahi kiya gaya hai. instituteBatchesData mein infinity: [] ke andar items add karein.</p>'}
    `;
}

function openTelegramChannel() {
    const url = 'https://t.me/limistudy';
    try {
        const w = window.open(url, '_blank');
        if (!w) window.location.href = url;
    } catch (e) {
        window.location.href = url;
    }
}

// X STUDY Support AI: app ke andar hi support/doubt chat khulta hai.
function openAIDoubtSolver() {
    const modal = document.getElementById('xstudy-ai-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    const messages = document.getElementById('xstudy-ai-messages');
    if (messages && !messages.dataset.started) {
        messages.dataset.started = '1';
        addXStudyAIMessage('bot', 'Namaste! 🤖 Main X STUDY Support AI hoon.\\n\\nMain app ke institute, categories, batches, All Classes, Description, Infinity Learning, login, logout aur navigation se related help kar sakta hoon. Aap apna doubt likhiye.');
    }
    setTimeout(() => document.getElementById('xstudy-ai-input')?.focus(), 80);
}

function closeAIDoubtSolver() {
    const modal = document.getElementById('xstudy-ai-modal');
    if (modal) modal.style.display = 'none';
}

function addXStudyAIMessage(type, text) {
    const box = document.getElementById('xstudy-ai-messages');
    if (!box) return;
    const div = document.createElement('div');
    div.className = 'xstudy-ai-msg ' + (type === 'user' ? 'xstudy-ai-user' : 'xstudy-ai-bot');
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function xStudyAIReply(message) {
    const q = String(message || '').toLowerCase().trim();
    const institute = currentInstitute || 'selected institute';
    const category = currentCategory || 'selected category';
    const batch = currentBatchDetails?.title || 'selected batch';

    if (!q) return 'Apna doubt likhiye, main help karta hoon. 😊';
    if (q.includes('batch') && (q.includes('add') || q.includes('kaise'))) return 'Naya batch add karne ke liye instituteBatchesData mein institute → category ke andar batch object add karein. Har batch mein title, image, classes, description aur infinity rakh sakte hain.';
    if (q.includes('all class') || q.includes('class add')) return 'Har batch ka All Classes alag hota hai. Us batch ke classes: [] ke andar jitni classes chahen add kar sakte hain.';
    if (q.includes('description')) return 'Har batch ki Description independent hai. Batch object mein description: "..." likhkar apna text add karein.';
    if (q.includes('infinity')) return 'Infinity Learning bhi batch-wise independent hai. Us batch ke infinity: [] mein jitne points chahen add kar sakte hain.';
    if (q.includes('login') || q.includes('logout')) return 'Login ke baad session browser storage mein save rehta hai. Logout karne par saved login clear ho jata hai aur dobara login kiya ja sakta hai.';
    if (q.includes('institute') && (q.includes('change') || q.includes('badal'))) return '☰ Menu/Profile → INSTITUTE se institute badal sakte hain. Current institute ke according categories aur batches load hote hain.';
    if (q.includes('back') || q.includes('wapas')) return 'Back arrow se batch/category screen se pichhli screen par wapas ja sakte hain.';
    if (q.includes('favourite') || q.includes('favorite')) return 'Batch card ke ❤️ button se favourite add/remove hota hai. Profile/Menu mein Favourite Batches se dekh sakte hain.';
    if (q.includes('telegram')) return 'Telegram quick button se X STUDY Telegram channel open hota hai.';
    if (q.includes('current') || q.includes('abhi')) return `Abhi selected context: Institute — ${institute}, Category — ${category}, Batch — ${batch}.`;
    return `Main X STUDY app support ke liye hoon. 😊 Aap institute, category, batch, All Classes, Description, Infinity Learning, login/logout, favourite ya navigation ke baare mein pooch sakte hain.\n\nCurrent context: ${institute} → ${category} → ${batch}.`;
}

function sendXStudyAIMessage(textFromChip) {
    const input = document.getElementById('xstudy-ai-input');
    const text = (textFromChip || (input && input.value) || '').trim();
    if (!text) return;
    if (input) input.value = '';
    addXStudyAIMessage('user', text);
    setTimeout(() => addXStudyAIMessage('bot', xStudyAIReply(text)), 220);
}

// 2. Batch Details Screen Open Karein
function openBatch(batchTitle) {
    document.getElementById('neet11-screen').style.display = 'none';
    document.getElementById('home-screen').style.display = 'none';

    currentBatchDetails = getCurrentBatchDetails(batchTitle);
    document.getElementById('selected-batch-title').innerText = batchTitle;
    document.getElementById('batch-details-screen').style.display = 'flex';

    renderBatchSubjects();
    renderBatchDescription(currentBatchDetails);
    renderInfinityLearning(currentBatchDetails);

    // Har naya batch khulte hi All Classes tab active rahega.
    const tabs = document.querySelectorAll('.batch-tab-item');
    tabs.forEach(t => {
        t.style.color = '#64748b';
        t.style.fontWeight = '600';
        t.style.borderBottom = 'none';
    });
    const classesTab = tabs[1];
    if (classesTab) {
        classesTab.style.color = '#4f46e5';
        classesTab.style.fontWeight = '700';
        classesTab.style.borderBottom = '3px solid #4f46e5';
    }
    document.getElementById('tab-content-desc').style.display = 'none';
    document.getElementById('tab-content-classes').style.display = 'flex';
    document.getElementById('tab-content-infinity').style.display = 'none';
}

// 3. Har batch ki apni All Classes list render hoti hai.
// Future mein kisi class ke andar lectures: [], notes: [], png: [], dpp: [] add karke content alag se manage kar sakte hain.
function renderBatchSubjects() {
    const container = document.getElementById('tab-content-classes');
    if (!container) return;
    container.innerHTML = '';

    const classes = (currentBatchDetails && Array.isArray(currentBatchDetails.classes))
        ? currentBatchDetails.classes
        : [];

    if (!classes.length) {
        container.innerHTML = `<div style="text-align:center; padding:40px 20px; color:#64748b; font-weight:600;">Is batch mein abhi All Classes add nahi ki gayi hain. Neeche instituteBatchesData mein classes: [] ke andar apni classes add karein.</div>`;
        return;
    }

    classes.forEach((sub) => {
        const safeName = String(sub.name || 'Class').replace(/'/g, "\'");
        const hasCounts = Object.prototype.hasOwnProperty.call(sub, 'classCount') || Object.prototype.hasOwnProperty.call(sub, 'notes');
        const classCount = Number.isFinite(Number(sub.classCount)) ? Number(sub.classCount) : 0;
        const noteCount = Number.isFinite(Number(sub.notes)) ? Number(sub.notes) : 0;
        const meta = hasCounts ? `<span>▣ Class: ${classCount}</span><span style="margin-left:18px;">▣ Notes: ${noteCount}</span>` : (sub.chapters || '');
        container.innerHTML += `
            <div onclick="openSubjectLectures('${safeName}')" style="position:relative; background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px 14px; display:flex; align-items:center; gap:14px; cursor:pointer; min-height:76px;">
                <div style="width:48px; height:48px; background:${sub.bg || '#eff6ff'}; border-radius:50%; display:flex; justify-content:center; align-items:center; font-size:19px; font-weight:700; color:#1597a8; flex-shrink:0;">${sub.icon || '📚'}</div>
                <div style="flex:1; min-width:0;">
                    <div style="font-size:17px; font-weight:500; color:#111827;">${sub.name || 'Class'}</div>
                    <div style="font-size:13px; color:#8a8a8a; margin-top:8px; white-space:nowrap;">${meta}</div>
                </div>
                ${sub.live ? '<div style="width:16px;height:16px;border-radius:50%;background:#ff3b30;position:absolute;right:58px;top:18px;"></div>' : ''}
                <div style="font-size:28px; color:#1597a8; font-weight:700;">›</div>
            </div>
        `;
    });
}

// 4. Batch Header Tabs Switch (Description / All Classes / Infinity)
function switchBatchTab(tabName, el) {
    const tabs = document.querySelectorAll('.batch-tab-item');
    tabs.forEach(t => {
        t.style.color = '#64748b';
        t.style.fontWeight = '600';
        t.style.borderBottom = 'none';
    });

    el.style.color = '#4f46e5';
    el.style.fontWeight = '700';
    el.style.borderBottom = '3px solid #4f46e5';

    document.getElementById('tab-content-desc').style.display = 'none';
    document.getElementById('tab-content-classes').style.display = 'none';
    document.getElementById('tab-content-infinity').style.display = 'none';

    document.getElementById('tab-content-' + tabName).style.display = (tabName === 'classes') ? 'flex' : 'block';
}

// 5. Teacher/Subject Click Karne Par Green Page Khulega
function openSubjectLectures(subjectName) {
    document.getElementById('batch-details-screen').style.display = 'none';
    currentSubjectDetails = (currentBatchDetails && Array.isArray(currentBatchDetails.classes))
        ? currentBatchDetails.classes.find(item => item.name === subjectName)
        : null;
    document.getElementById('video-batch-title').innerText = subjectName;
    document.getElementById('video-screen').style.display = 'flex';
    renderSubjectLectures();
    renderSubjectResourceTab('notes');
    renderSubjectResourceTab('png');
    renderSubjectResourceTab('dpp');
    switchSubjectTab('lectures', document.querySelector('.sub-tab'));
}

function openInYouTube(url) {
    if (!url) return;
    window.open(url, '_system');
}


function renderSubjectLectures() {
    const container = document.getElementById('sub-tab-lectures');
    if (!container) return;
    container.innerHTML = "";

    const lectures = (currentSubjectDetails && Array.isArray(currentSubjectDetails.lectures) && currentSubjectDetails.lectures.length)
        ? currentSubjectDetails.lectures : sampleLecturesData;
    lectures.forEach((lec) => {
        let videoId = "";
        if (lec.youtubeUrl) {
            const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
            const match = lec.youtubeUrl.match(regExp);
            videoId = (match && match[2].length === 11) ? match[2] : "";
        }

        // maxresdefault.jpg direct YouTube banner poster fetch karta hai
        const autoThumb = videoId 
            ? `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`
            : 'https://via.placeholder.com/110x70';

        container.innerHTML += `
            <div onclick="openInYouTube('${lec.youtubeUrl}')" style="background:#ffffff; border:1.5px solid #2d6a4f; border-radius:16px; padding:12px; display:flex; align-items:center; gap:12px; box-shadow:0 2px 5px rgba(0,0,0,0.04); cursor:pointer;">
                <div style="position:relative; width:110px; height:70px; border-radius:10px; overflow:hidden; flex-shrink:0; background:#e2e8f0;">
                    <!-- Fallback: Agar maxres unavailable ho toh hqdefault load ho jaye -->
                    <img src="${autoThumb}" style="width:100%; height:100%; object-fit:cover;" onerror="this.src='https://img.youtube.com/vi/${videoId}/hqdefault.jpg';" />
                    <span style="position:absolute; bottom:4px; right:4px; background:rgba(0,0,0,0.75); color:#fff; font-size:10px; padding:2px 4px; border-radius:4px; font-weight:700;">${lec.duration}</span>
                </div>
                <div style="flex:1;">
                    <h4 style="margin:0 0 8px 0; font-size:14px; font-weight:800; color:#0f172a; line-height:1.3;">${lec.title}</h4>
                    <div style="display:flex; align-items:center; gap:6px; font-size:12px; color:#64748b; font-weight:600;">
                        <span>📅</span>
                        <span>${lec.date}</span>
                    </div>
                </div>
            

</div>
        `;
    });
}




function renderSubjectResourceTab(tabName) {
    const container = document.getElementById('sub-tab-' + tabName);
    if (!container) return;
    const items = currentSubjectDetails && Array.isArray(currentSubjectDetails[tabName]) ? currentSubjectDetails[tabName] : [];
    if (!items.length) {
        const labels = { notes: '📄 Class Notes', png: '🖼️ Class PNG Slides', dpp: '📝 DPP PDFs' };
        container.innerHTML = `<div onclick="alert('${tabName.toUpperCase()} content can be added in the class object.')" style="background:#ffffff; padding:16px; border-radius:12px; border:1.5px solid #2d6a4f; color:#2d6a4f; font-weight:600; cursor:pointer;">${labels[tabName]} Available Soon</div>`;
        return;
    }
    container.innerHTML = items.map((item, i) => {
        const title = typeof item === 'string' ? item : (item.title || `Item ${i+1}`);
        const url = typeof item === 'string' ? '' : (item.url || item.youtubeUrl || '');
        const safeTitle = String(title).replace(/'/g, "\'");
        const action = url ? `window.open('${String(url).replace(/'/g, "\'")}', '_system')` : `alert('Open: ${safeTitle}')`;
        return `<div onclick="${action}" style="background:#ffffff; padding:14px; border-radius:12px; border:1.5px solid #2d6a4f; color:#2d6a4f; font-weight:700; cursor:pointer;">${title}</div>`;
    }).join('');
}

// 7. Green Page Ke Tabs Switch Karein (LECTURES, NOTES, PNG, DPP)
function switchSubjectTab(tabName, el) {
    const tabs = document.querySelectorAll('.sub-tab');
    tabs.forEach(t => {
        t.style.color = '#d8f3dc';
        t.style.fontWeight = '600';
        t.style.borderBottom = '3px solid transparent';
    });

    el.style.color = '#ffffff';
    el.style.fontWeight = '700';
    el.style.borderBottom = '3px solid #74c69d';

    document.getElementById('sub-tab-lectures').style.display = 'none';
    document.getElementById('sub-tab-notes').style.display = 'none';
    document.getElementById('sub-tab-png').style.display = 'none';
    document.getElementById('sub-tab-dpp').style.display = 'none';

    document.getElementById('sub-tab-' + tabName).style.display = 'flex';
}

// 8. Back Buttons Navigation
function closeBatchDetails() {
    document.getElementById('batch-details-screen').style.display = 'none';
    document.getElementById('video-screen').style.display = 'none';
    document.getElementById('neet11-screen').style.display = 'flex';
    renderNEET11Batches();
}

// 6. Close Video Screen (Updated Back to Batch Details)
function closeVideoScreen() {
    const player = document.getElementById('video-player');
    if (player) {
        const currentSrc = player.src;
        player.src = '';
        player.src = currentSrc;
    }

    document.getElementById('video-screen').style.display = 'none';
    document.getElementById('batch-details-screen').style.display = 'flex';
}
function openNEET11() {
    currentCategory = currentCategory || 'NEET 11th';
    document.getElementById('home-screen').style.display = 'none';
    document.getElementById('lecture-screen').style.display = 'none';
    document.getElementById('neet11-screen').style.display = 'flex';
    const titleEl = document.getElementById('category-screen-title');
    if (titleEl) titleEl.innerText = currentCategory;
    window.scrollTo(0, 0);
    renderNEET11Batches();
}

function closeNEET11() {
    document.getElementById('neet11-screen').style.display = 'none';
    document.getElementById('lecture-screen').style.display = 'flex';
    window.scrollTo(0, 0);
}
function toggleFavourite(index) {
    let favourites = JSON.parse(xStorage.getItem('limiFavouriteBatches') || '[]');
    const activeBatches = getCurrentBatches();
    const batch = activeBatches[index];

    if (!batch) return;

    const existingIndex = favourites.findIndex(item =>
        item.title === batch.title &&
        (item.institute || currentInstitute) === currentInstitute &&
        (item.category || currentCategory) === currentCategory
    );

    if (existingIndex !== -1) {
        favourites.splice(existingIndex, 1);
    } else {
        favourites.push({
            ...batch,
            institute: currentInstitute,
            category: currentCategory
        });
    }

    xStorage.setItem('limiFavouriteBatches', JSON.stringify(favourites));
    renderNEET11Batches();
}
// 3. Back Button Functionality
        function closeLectures() {
            document.getElementById('lecture-screen').style.display = 'none';
            document.getElementById('home-screen').style.display = 'block';
        }
        // Dynamic Ads Data Config
const adsData = [
    {
        title: "Join Our WhatsApp Group",
        desc: "Get latest updates, PDF notes, and lecture alerts daily!",
        btnText: "JOIN WHATSAPP",
        link: "https://whatsapp.com/channel/0029Vb8zzqBK0IBjbxi16t22", // Apna WhatsApp link yahan dalein
        bg: "linear-gradient(135deg, #25d366, #128c7e)",
        btnColor: "#128c7e"
    },
    {
        title: "Subscribe YouTube Channel",
        desc: "Watch free video lectures, solution series & strategy tips!",
        btnText: "WATCH YOUTUBE",
        link: "https://www.youtube.com/@helptogethercentre", // Apna YouTube link yahan dalein
        bg: "linear-gradient(135deg, #ff0000, #990000)",
        btnColor: "#ff0000"
    },
    {
        title: "Join Telegram Channel",
        desc: "Download free Study Material, DPPs & Test Series PDFs!",
        btnText: "JOIN TELEGRAM",
        link:"https://t.me/limistudy", // Apna Telegram link yahan dalein
        bg: "linear-gradient(135deg, #0088cc, #005580)",
        btnColor: "#0088cc"
    }
];

let currentAdIndex = 0;

function rotateAds() {
    currentAdIndex = (currentAdIndex + 1) % adsData.length;
    const ad = adsData[currentAdIndex];
    
    const bannerBox = document.getElementById('ad-banner-box');
    const titleEl = document.getElementById('ad-title');
    const descEl = document.getElementById('ad-desc');
    const linkEl = document.getElementById('ad-link');

    if (bannerBox && titleEl) {
        bannerBox.style.background = ad.bg;
        titleEl.innerText = ad.title;
        descEl.innerText = ad.desc;
        linkEl.innerText = ad.btnText;
        linkEl.href = ad.link;
        linkEl.style.color = ad.btnColor;
    }
}

// Every 4 Seconds Ad Auto-Change Hoga
setInterval(rotateAds, 4000);
  function openMenuScreen() {
    menuReturnScreen = document.getElementById('lecture-screen').style.display !== 'none' ? 'lecture-screen' : 'home-screen';
    document.getElementById('lecture-screen').style.display = 'none';
    document.getElementById('home-screen').style.display = 'none';
    document.getElementById('menu-screen').style.display = 'flex';
}

function closeMenuScreen() {
    document.getElementById('menu-screen').style.display = 'none';
    const target = document.getElementById(menuReturnScreen || 'lecture-screen');
    if (target) target.style.display = 'flex';
}
function openVideoPlayer(title) {
    // 1. Pehle sabhi screens ko hide karein taaki overlapping na ho
    document.getElementById('home-screen').style.display = 'none';
    document.getElementById('lang-screen').style.display = 'none';

    // 2. Ab dedicated Video Screen ko show karein
    const videoScreen = document.getElementById('video-screen');
    videoScreen.style.display = 'flex';
}
// Category box click: current institute + selected category ke exact batches show honge.
function openCategoryBatches(categoryName) {
    currentCategory = categoryName;
    xStorage.setItem('xstudySelectedCategory', categoryName);

    const titleEl = document.getElementById('category-screen-title');
    if (titleEl) titleEl.innerText = categoryName;

    const home = document.getElementById('home-screen');
    const lecture = document.getElementById('lecture-screen');
    const batchScreen = document.getElementById('neet11-screen');

    if (home) home.style.display = 'none';
    if (lecture) lecture.style.display = 'none';
    if (batchScreen) batchScreen.style.display = 'flex';

    window.scrollTo(0, 0);
    renderNEET11Batches();
}

// Register X STUDY PWA service worker when supported.
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js').catch(() => {});
    });
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_LAYOUT + HTML_BODY_START + HTML_BODY_END)

@app.route('/manifest.webmanifest')
def manifest():
    data = {
        'name': 'X STUDY', 'short_name': 'X STUDY',
        'description': 'X STUDY - Your Study Buddy for a Better Tomorrow',
        'start_url': '/', 'scope': '/', 'display': 'standalone',
        'background_color': '#000000', 'theme_color': '#000000',
        'orientation': 'portrait-primary',
        'icons': [
            {'src': '/xstudy_icon_192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': '/xstudy_icon.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}
        ]
    }
    return Response(json.dumps(data), mimetype='application/manifest+json')

@app.route('/service-worker.js')
def service_worker():
    sw = "const CACHE_NAME = 'x-study-v1';\n"          "const APP_SHELL = ['/', '/manifest.webmanifest', '/xstudy_icon.png', '/xstudy_icon_192.png'];\n"          "self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())); });\n"          "self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))).then(() => self.clients.claim())); });\n"          "self.addEventListener('fetch', event => { if (event.request.method !== 'GET') return; event.respondWith(fetch(event.request).then(response => { const copy = response.clone(); caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy)).catch(() => {}); return response; }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/')))); });\n"
    return Response(sw, mimetype='application/javascript')

@app.route('/xstudy_icon.png')
def xstudy_icon():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'xstudy_icon.png')

@app.route('/xstudy_icon_192.png')
def xstudy_icon_192():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'xstudy_icon_192.png')

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.json or {}
    identifier = data.get('identifier', '').strip()
    
    if not identifier:
        return jsonify({'success': False, 'message': 'Email address required'})

    otp = str(random.randint(1000, 9999))
    otp_store[identifier] = {
        'code': otp,
        'created_at': time.time()
    }

    try:
        api_key = app.config['BREVO_API_KEY']
        sender_email = app.config['BREVO_SENDER_EMAIL']
        sender_name = app.config['BREVO_SENDER_NAME']

        if not api_key or not sender_email:
            otp_store.pop(identifier, None)
            return jsonify({
                'success': False,
                'message': 'Email service is not configured. Please contact support.'
            })

        email_payload = {
            'sender': {
                'name': sender_name,
                'email': sender_email
            },
            'to': [
                {'email': identifier}
            ],
            'subject': 'X STUDY Verification OTP',
            'textContent': (
                f'Your X STUDY App OTP Code is: {otp}\n\n'
                'Valid for 20 minutes. Do not share this code with anyone.'
            ),
            'htmlContent': (
                '<div style="font-family:Arial,sans-serif;line-height:1.6">'
                '<h2 style="margin-bottom:8px">X STUDY Verification</h2>'
                f'<p>Your OTP Code is:</p><p style="font-size:28px;font-weight:700;letter-spacing:6px">{otp}</p>'
                '<p>Valid for 20 minutes. Do not share this code with anyone.</p>'
                '</div>'
            )
        }

        api_request = urllib.request.Request(
            'https://api.brevo.com/v3/smtp/email',
            data=json.dumps(email_payload).encode('utf-8'),
            headers={
                'accept': 'application/json',
                'api-key': api_key,
                'content-type': 'application/json'
            },
            method='POST'
        )

        with urllib.request.urlopen(api_request, timeout=15) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f'Email API returned HTTP {response.status}')

        return jsonify({'success': True, 'message': 'OTP Sent Successfully!'})
    except Exception as e:
        otp_store.pop(identifier, None)
        print(f'OTP email API error: {type(e).__name__}: {e}')
        return jsonify({
            'success': False,
            'message': 'Unable to send OTP right now. Please try again.'
        })

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json or {}
    identifier = data.get('identifier', '').strip()
    user_otp = str(data.get('otp', '')).strip()
    
    record = otp_store.get(identifier)
    
    if not record:
        return jsonify({'success': False, 'message': 'No OTP requested for this Email'})

    if time.time() - record['created_at'] > 1200:
        return jsonify({'success': False, 'message': 'OTP Expired! Please click Resend'})

    if str(record['code']).strip() == user_otp:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Invalid OTP Code'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
