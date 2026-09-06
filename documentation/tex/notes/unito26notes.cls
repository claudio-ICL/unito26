%% unito26notes -- class for the lecture notes of `Python for Finance'.
%% This file owns the whole preamble: content files carry none.
\LoadClass[11pt,oneside,a4paper,table]{book}

%% INPUT PATHS %%
% Declared once, so that \input{filename} never carries a directory.
% Add one line per chapter directory.
\makeatletter
\def\input@path{
    {./}{../}
    {../include/}
    {./orderdriven/}
    {./orderdriven/sections/}
    {./hawkes/}
    {./hawkes/sections/}
}
\makeatother

%% TEXT ENCODING %%
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[english]{babel}
\usepackage{mathpazo}
%% COLOR %%
\usepackage[table]{xcolor}
\usepackage[breakable]{tcolorbox}
%% MARGINS %%
\usepackage[margin=3.00cm]{geometry}
%% BIBLIOGRAPHY %%
\usepackage[round,sort,comma,numbers,authoryear]{natbib}
\setcitestyle{aysep={ },yysep={,}}
%% FIGURES AND GRAPHICS %%
\usepackage{graphicx}
\graphicspath{
    {./figures/}
    {./orderdriven/figures/}
    {./hawkes/figures/}
}
\usepackage{booktabs}
\usepackage{pdflscape} %make landscape orientation available
\usepackage{afterpage}
\usepackage{capt-of}
\usepackage{makecell}
\usepackage[Export]{adjustbox} % Used to constrain images to a maximum size
\adjustboxset{max size={0.9\linewidth}{0.9\paperheight}}
%% ALGORITHMS %%
\usepackage{algorithm, algorithmic}
%% AMS %%
\usepackage{amsmath}
\usepackage{amsthm}
\usepackage{amsfonts}
\usepackage{amssymb}
\usepackage{mathrsfs}
\usepackage{xfrac}
\usepackage{esint}

\setlength{\parskip}{7pt}
\setlength{\parindent}{0pt}
\setlength{\headheight}{15pt}

%% THEOREM ENVIRONMENTS %%
% One shared counter, numbered within section.
\theoremstyle{definition}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{thm}[theorem]{Theorem}
\newtheorem{corol}[theorem]{Corollary}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{prop}[theorem]{Proposition}
\newtheorem{conjecture}[theorem]{Conjecture}
\newtheorem{model}[theorem]{Model}
\newtheorem{defi}[theorem]{Definition}
\newtheorem{remark}[theorem]{Remark}
\newtheorem{example}[theorem]{Example}
\newtheorem{exercise}[theorem]{Exercise}
\newtheorem{assumption}[theorem]{Assumption}
\newtheorem{approximation}[theorem]{Approximation}

%% MISCELLANEOUS %%
\usepackage{appendix}
\usepackage{fancyhdr, float, enumerate, longtable, upquote, mathtools, setspace, tikz}
\usepackage{multirow}
\usepackage[inline]{enumitem}
\sloppy %Prevents overflowing lines

\definecolor{unitoblue}{rgb}{0.000, 0.243, 0.455}
\definecolor{chaptergrey}{rgb}{0.000, 0.243, 0.455}

\setcounter{secnumdepth}{3}
\numberwithin{algorithm}{section}
\numberwithin{equation}{section}
