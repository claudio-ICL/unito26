%% unito26questions -- class for the sample examination questions of `Python for Finance'.
%% This file owns the whole preamble: content files carry none.
\LoadClass[11pt,oneside,a4paper]{article}

%% INPUT PATHS %%
% Declared once, so that \input{filename} never carries a directory.
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
\usepackage{mathpazo}
%% COLOR %%
\usepackage[table]{xcolor}
%% MARGINS %%
\usepackage[margin=2.50cm]{geometry}
%% AMS %%
\usepackage{amsmath}
\usepackage{amsthm}
\usepackage{amsfonts}
\usepackage{amssymb}
\usepackage{mathrsfs}
\usepackage{xfrac}
\usepackage{mathtools}
%% BIBLIOGRAPHY %%
% No citation of its own: natbib defines the \citealp that titles of the notes' labels carry.
\usepackage[round,sort,comma,numbers,authoryear]{natbib}
%% TABLES AND LISTS %%
\usepackage{booktabs, longtable, array, multirow, upquote, needspace}
\usepackage[inline]{enumitem}
\sloppy

\setlength{\parskip}{6pt}
\setlength{\parindent}{0pt}

%% THE NOTES, BY REFERENCE %%
% A question cites the notes by label, as \ref{notes:corol.meanResponse},
% so that its numbers are the notes' numbers whenever the notes change.
% The labels are read from the notes' last build, which therefore comes first.
% Every chapter is named: the notes' main.aux reaches them by paths relative to notes/.
% They are read once the notation is loaded, since some of them carry its macros.
\usepackage{xr-hyper}
\AtBeginDocument{%
 \externaldocument[notes:][../notes/main.pdf]{../notes/welcome/welcome}%
 \externaldocument[notes:][../notes/main.pdf]{../notes/microstructure/microstructure}%
 \externaldocument[notes:][../notes/main.pdf]{../notes/appendix/appendix}%
 \externaldocument[notes:][../notes/main.pdf]{../notes/appendix/objects}}

%% THE VERSION LINE %%
% babel's `english' sets \today in the American form; the questions are British throughout.
\newcommand{\compilationDate}{%
 \number\day\space
 \ifcase\month\or January\or February\or March\or April\or May\or June\or
 July\or August\or September\or October\or November\or December\fi
 \space\number\year}

%% QUESTIONS %%
% A question is numbered within its section and offers lettered choices,
% exactly one of which is written \correctchoice.
% Its \explanation closes it and writes its row of the key, which \printkey sets at the end:
% the letter of that row is the letter the correct choice is printed with, and is never typed.
% \notebook{<name>}, once at the head of a section, names the notebook that verifies it.
\makeatletter
\newcounter{question}[section]
\renewcommand{\thequestion}{\thesection.\arabic{question}}
\newlist{choices}{enumerate}{1}
\setlist[choices]{label=(\Alph*), ref=\Alph*, itemsep=2pt, topsep=4pt}
\let\questions@key\relax
\newcommand{\questions@keyrows}{}
\newenvironment{question}{%
  \par\addvspace{14pt}%
  \needspace{8\baselineskip}%
  \refstepcounter{question}%
  \global\let\questions@key\relax
  \noindent\textbf{Question~\thequestion}\par\nobreak
}{%
  \ifx\questions@key\relax\else
    \ClassError{unito26questions}{Question \thequestion\space has no explanation}{}%
  \fi
  \par
}
\newcommand{\choice}{\item}
\newcommand{\correctchoice}{%
  \item
  \ifx\questions@key\relax\else
    \ClassError{unito26questions}{Question \thequestion\space has two correct choices}{}%
  \fi
  \xdef\questions@key{\Alph{choicesi}}%
}
\newcommand{\explanation}[1]{%
  \ifx\questions@key\relax
    \ClassError{unito26questions}{Question \thequestion\space has no correct choice}{}%
  \fi
  \edef\questions@row{\noexpand\keyrow{\thequestion}{\questions@key}}%
  \expandafter\g@addto@macro\expandafter\questions@keyrows\expandafter{\questions@row{#1}}%
  \global\let\questions@key\relax
}
\newcommand{\notebook}[1]{%
  \edef\questions@row{\noexpand\keysection{\thesection}{#1}}%
  \expandafter\g@addto@macro\expandafter\questions@keyrows\expandafter{\questions@row}%
}
\newcommand{\keysection}[2]{%
  \multicolumn{3}{@{}>{\raggedright\arraybackslash}p{\textwidth}@{}}{\rule{0pt}{18pt}\textbf{Section~#1},
  verified by \texttt{notebooks/sample-questions/#2.ipynb}}\\[2pt]}
\newcommand{\keyrow}[3]{#1 & #2 & #3 \\[2pt]}
\newcommand{\printkey}{%
  \clearpage
  \section*{Solution key}
  \addcontentsline{toc}{section}{Solution key}
  \begin{longtable}{@{}l c >{\raggedright\arraybackslash}p{0.76\textwidth}@{}}
   \toprule
   Question & Answer & Why \\
   \midrule
   \endhead
   \questions@keyrows
   \bottomrule
  \end{longtable}}

%% ONE TOPIC ALONE %%
% A build started as
%   latexmk -pdf -jobname=check-<topic> -usepretex='\def\onlytopic{<topic>}' main.tex
% sets the questions of sections/<topic>.tex alone, under a job name of its own,
% so that topics written at the same time are checked without sharing an .aux.
\ifdefined\onlytopic
  \AtBeginDocument{%
    \let\questions@input\input
    \renewcommand{\input}[1]{%
      \def\questions@file{#1}%
      \ifx\questions@file\onlytopic\questions@input{#1}\fi}}
\fi
\makeatother
