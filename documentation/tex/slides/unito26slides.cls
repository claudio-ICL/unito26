%% unito26slides -- beamer class for the slides of `Python for Finance'.
%% Modelled on the beamer class of Claudio's viva.
%% This file owns the whole preamble: content files carry none.
\LoadClass[10pt]{beamer}

%% INPUT PATHS %%
\makeatletter
\def\input@path{
    {./}{../}
    {../include/}
    {./sections/}
}
\makeatother

%% TEXT ENCODING %%
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[english]{babel}
%% BIBLIOGRAPHY %%
\usepackage[round,sort,comma,numbers,authoryear]{natbib}
\setcitestyle{aysep={ },yysep={,}}
%% FIGURES AND GRAPHICS %%
\usepackage{graphicx}
\graphicspath{
    {./figures/}
    {../notes/lob/figures/}
}
\usepackage{booktabs}
\usepackage{makecell}
\usepackage[Export]{adjustbox}
\adjustboxset{max size={\linewidth}{\paperheight}}
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

%% THEOREM ENVIRONMENTS %%
% Same names as the notes, so that a statement can be moved between the two.
\newtheorem{thm}{Theorem}
\newtheorem{corol}[thm]{Corollary}
\newtheorem{prop}[thm]{Proposition}
\newtheorem{model}[thm]{Model}
\newtheorem{conjecture}[thm]{Conjecture}
\newtheorem{defi}[thm]{Definition}
\newtheorem{remark}[thm]{Remark}
\newtheorem{exercise}[thm]{Exercise}
\newtheorem{assumption}[thm]{Assumption}
% `example' and `corollary' are already provided by beamer.
\setbeamertemplate{theorems}[numbered]

%% MISCELLANEOUS %%
\usepackage{float, enumerate, longtable, booktabs, upquote, mathtools, setspace, tikz}
\sloppy %Prevents overflowing lines
