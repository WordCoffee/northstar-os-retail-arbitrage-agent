# 18 — Incident-Response Runbook (1C-06 beta)

**Named accountable role:** Tyrone (single operator — sole rollback, sole approval, sole operational authority)

## Access Disable Steps

-
 
1
.
 
S
e
t
 
t
h
e
 
a
f
f
e
c
t
e
d
 
o
r
g
a
n
i
z
a
t
i
o
n
 
a
c
t
i
v
e
=
0
 
(
s
u
s
p
e
n
d
)
.## Access Disable Steps

-
 
2
.
 
S
e
t
 
t
h
e
 
a
f
f
e
c
t
e
d
 
m
e
m
b
e
r
s
h
i
p
s
 
s
t
a
t
u
s
=
'
s
u
s
p
e
n
d
e
d
'
 
(
o
r
 
'
r
e
v
o
k
e
d
'
)
.## Access Disable Steps

-
 
3
.
 
C
o
n
f
i
r
m
 
t
h
e
 
a
f
f
e
c
t
e
d
 
p
r
o
v
i
d
e
r
 
r
o
w
s
 
h
a
v
e
 
e
n
a
b
l
e
d
=
0
 
(
l
o
c
a
l
/
f
a
k
e
 
h
a
n
d
l
e
r
s
 
n
e
v
e
r
 
n
e
e
d
 
l
i
v
e
 
p
r
o
v
i
d
e
r
s
)
.## Access Disable Steps

-
 
4
.
 
I
f
 
b
e
t
a
 
a
c
c
e
p
t
a
n
c
e
 
e
n
f
o
r
c
e
m
e
n
t
 
i
s
 
o
n
,
 
d
o
 
n
o
t
 
c
h
a
n
g
e
 
i
t
 
—
 
s
u
s
p
e
n
s
i
o
n
 
a
l
r
e
a
d
y
 
b
l
o
c
k
s
 
a
u
t
h
e
n
t
i
c
a
t
e
d
 
u
s
e
.## Session Invalidation

-
 
1
.
 
R
e
v
o
k
e
 
t
h
e
 
a
f
f
e
c
t
e
d
 
j
t
i
(
s
)
:
 
P
O
S
T
 
/
s
e
s
s
i
o
n
/
r
e
v
o
k
e
?
j
t
i
=
<
j
t
i
>
 
(
o
w
n
e
r
 
o
r
 
o
p
e
r
a
t
o
r
)
.## Session Invalidation

-
 
2
.
 
R
e
v
o
k
e
 
A
L
L
 
s
e
s
s
i
o
n
s
 
f
o
r
 
t
h
e
 
a
f
f
e
c
t
e
d
 
u
s
e
r
 
b
y
 
m
a
r
k
i
n
g
 
e
v
e
r
y
 
r
o
w
 
i
n
 
t
h
e
 
s
e
s
s
i
o
n
s
 
t
a
b
l
e
 
f
o
r
 
t
h
a
t
 
u
s
e
r
 
a
s
 
r
e
v
o
k
e
d
 
(
o
p
e
r
a
t
o
r
 
S
Q
L
)
.## Session Invalidation

-
 
3
.
 
C
o
n
f
i
r
m
:
 
a
 
r
e
q
u
e
s
t
 
w
i
t
h
 
a
 
r
e
v
o
k
e
d
 
t
o
k
e
n
 
r
e
t
u
r
n
s
 
4
0
1
.## Secret Rotation Checklist

-
 
1
.
 
R
o
t
a
t
e
 
t
h
e
 
a
f
f
e
c
t
e
d
 
s
e
c
r
e
t
 
(
e
.
g
.
,
 
N
O
R
T
H
S
T
A
R
_
J
W
T
_
S
E
C
R
E
T
 
o
r
 
a
 
c
r
e
d
e
n
t
i
a
l
)
 
—
 
g
e
n
e
r
a
t
e
 
a
 
n
e
w
 
v
a
l
u
e
;
 
N
E
V
E
R
 
r
e
u
s
e
 
t
h
e
 
o
l
d
 
o
n
e
.## Secret Rotation Checklist

-
 
2
.
 
U
p
d
a
t
e
 
t
h
e
 
e
n
c
r
y
p
t
e
d
 
v
a
u
l
t
 
(
f
o
u
n
d
a
t
i
o
n
/
s
e
c
r
e
t
s
.
p
y
)
 
i
f
 
t
h
e
 
s
e
c
r
e
t
 
i
s
 
s
t
o
r
e
d
 
t
h
e
r
e
.## Secret Rotation Checklist

-
 
3
.
 
R
e
s
t
a
r
t
 
t
h
e
 
b
a
c
k
e
n
d
/
w
o
r
k
e
r
/
s
c
h
e
d
u
l
e
r
 
s
o
 
t
h
e
 
n
e
w
 
s
e
c
r
e
t
 
i
s
 
l
o
a
d
e
d
.## Secret Rotation Checklist

-
 
4
.
 
V
e
r
i
f
y
 
o
l
d
 
t
o
k
e
n
s
 
n
o
w
 
f
a
i
l
 
(
4
0
1
)
 
a
n
d
 
n
e
w
 
t
o
k
e
n
s
 
w
o
r
k
.## Secret Rotation Checklist

-
 
5
.
 
I
f
 
a
 
s
e
c
r
e
t
 
w
a
s
 
e
x
p
o
s
e
d
,
 
t
r
e
a
t
 
t
h
e
 
e
n
v
i
r
o
n
m
e
n
t
 
a
s
 
c
o
m
p
r
o
m
i
s
e
d
 
a
n
d
 
r
e
v
o
k
e
 
a
l
l
 
s
e
s
s
i
o
n
s
.## Evidence And Log Preservation

-
 
1
.
 
E
x
p
o
r
t
 
t
h
e
 
r
e
l
e
v
a
n
t
 
a
u
d
i
t
 
e
v
e
n
t
s
 
(
a
c
t
i
o
n
=
a
u
t
h
z
.
d
e
n
i
e
d
,
 
s
e
s
s
i
o
n
.
*
,
 
j
o
b
.
s
t
a
t
e
.
*
)
 
w
i
t
h
 
c
o
r
r
e
l
a
t
i
o
n
/
r
e
q
u
e
s
t
 
i
d
s
 
t
o
 
a
 
r
e
a
d
-
o
n
l
y
 
l
o
c
a
t
i
o
n
.## Evidence And Log Preservation

-
 
2
.
 
P
r
e
s
e
r
v
e
 
t
h
e
 
f
o
u
n
d
a
t
i
o
n
 
D
B
 
(
p
g
_
d
u
m
p
)
 
B
E
F
O
R
E
 
a
n
y
 
r
e
m
e
d
i
a
t
i
o
n
 
w
r
i
t
e
 
w
h
e
r
e
 
p
o
s
s
i
b
l
e
.## Evidence And Log Preservation

-
 
3
.
 
N
o
t
e
 
t
h
e
 
e
x
a
c
t
 
t
i
m
e
s
t
a
m
p
s
,
 
t
o
k
e
n
s
 
(
j
t
i
)
,
 
a
n
d
 
r
e
q
u
e
s
t
s
 
i
n
v
o
l
v
e
d
.## Evidence And Log Preservation

-
 
4
.
 
D
o
 
n
o
t
 
d
e
l
e
t
e
 
l
o
g
s
 
d
u
r
i
n
g
 
a
n
 
a
c
t
i
v
e
 
i
n
c
i
d
e
n
t
.## Scope Assessment

-
 
1
.
 
W
h
i
c
h
 
u
s
e
r
s
/
o
r
g
a
n
i
z
a
t
i
o
n
s
 
w
e
r
e
 
a
f
f
e
c
t
e
d
?
 
(
q
u
e
r
y
 
s
e
s
s
i
o
n
s
 
+
 
a
c
c
e
p
t
a
n
c
e
_
e
v
e
n
t
s
 
+
 
a
u
d
i
t
 
b
y
 
c
o
r
r
e
l
a
t
i
o
n
 
i
d
)
.## Scope Assessment

-
 
2
.
 
W
h
i
c
h
 
d
a
t
a
 
c
o
u
l
d
 
h
a
v
e
 
b
e
e
n
 
e
x
p
o
s
e
d
?
 
(
m
a
p
 
t
o
 
t
h
e
 
d
a
t
a
 
i
n
v
e
n
t
o
r
y
)
.## Scope Assessment

-
 
3
.
 
W
a
s
 
a
n
y
 
w
r
i
t
e
 
p
e
r
f
o
r
m
e
d
?
 
(
a
u
d
i
t
 
j
o
b
.
s
t
a
t
e
.
*
 
+
 
k
e
y
w
o
r
d
.
i
m
p
o
r
t
 
+
 
s
c
h
e
d
u
l
e
.
*
)
.## Scope Assessment

-
 
4
.
 
W
a
s
 
a
n
y
 
p
r
o
v
i
d
e
r
/
m
a
r
k
e
t
p
l
a
c
e
 
o
p
e
r
a
t
i
o
n
 
p
o
s
s
i
b
l
e
?
 
(
p
r
o
v
i
d
e
r
s
 
a
r
e
 
d
i
s
a
b
l
e
d
;
 
c
o
n
f
i
r
m
)
.## Customer Communication Decision Tree

-
 
W
a
s
 
a
n
y
 
c
u
s
t
o
m
e
r
 
d
a
t
a
 
a
c
c
e
s
s
e
d
 
b
y
 
a
n
 
u
n
a
u
t
h
o
r
i
z
e
d
 
p
a
r
t
y
?## Customer Communication Decision Tree

-
 
 
 
-
 
Y
E
S
 
a
n
d
 
e
v
i
d
e
n
c
e
 
e
x
i
s
t
s
 
-
>
 
n
o
t
i
f
y
 
t
h
e
 
a
f
f
e
c
t
e
d
 
o
r
g
a
n
i
z
a
t
i
o
n
 
p
r
o
m
p
t
l
y
 
w
i
t
h
 
f
a
c
t
s
 
a
n
d
 
n
e
x
t
 
s
t
e
p
s
.## Customer Communication Decision Tree

-
 
 
 
-
 
Y
E
S
 
b
u
t
 
s
c
o
p
e
 
u
n
c
e
r
t
a
i
n
 
-
>
 
n
o
t
i
f
y
 
w
i
t
h
 
c
o
n
s
e
r
v
a
t
i
v
e
 
l
a
n
g
u
a
g
e
;
 
d
o
 
n
o
t
 
o
v
e
r
-
c
l
a
i
m
 
c
e
r
t
a
i
n
t
y
.## Customer Communication Decision Tree

-
 
 
 
-
 
N
O
 
(
c
o
n
t
a
i
n
e
d
 
b
e
f
o
r
e
 
a
c
c
e
s
s
)
 
-
>
 
n
o
 
n
o
t
i
f
i
c
a
t
i
o
n
 
r
e
q
u
i
r
e
d
;
 
d
o
c
u
m
e
n
t
 
t
h
e
 
n
e
a
r
-
m
i
s
s
.## Customer Communication Decision Tree

-
 
W
a
s
 
t
h
e
r
e
 
a
 
s
e
r
v
i
c
e
 
o
u
t
a
g
e
 
/
 
d
a
t
a
 
l
o
s
s
?
 
-
>
 
n
o
t
i
f
y
 
p
e
r
 
S
L
A
 
e
x
p
e
c
t
a
t
i
o
n
s
 
o
f
 
t
h
e
 
b
e
t
a
 
c
o
n
t
r
a
c
t
.## Customer Communication Decision Tree

-
 
I
s
 
a
 
l
e
g
a
l
/
r
e
g
u
l
a
t
o
r
y
 
n
o
t
i
f
i
c
a
t
i
o
n
 
o
b
l
i
g
a
t
i
o
n
 
t
r
i
g
g
e
r
e
d
?
 
-
>
 
e
s
c
a
l
a
t
e
 
t
o
 
t
h
e
 
n
a
m
e
d
 
a
c
c
o
u
n
t
a
b
l
e
 
r
o
l
e
 
(
a
n
d
 
c
o
u
n
s
e
l
 
i
f
 
e
n
g
a
g
e
d
)
;
 
d
o
 
n
o
t
 
g
u
e
s
s
.## Recovery

-
 
1
.
 
A
p
p
l
y
 
t
h
e
 
d
o
c
u
m
e
n
t
e
d
 
a
c
c
e
s
s
-
d
i
s
a
b
l
e
 
s
t
e
p
s
 
i
n
 
r
e
v
e
r
s
e
 
o
n
l
y
 
a
f
t
e
r
 
r
o
o
t
 
c
a
u
s
e
 
i
s
 
u
n
d
e
r
s
t
o
o
d
.## Recovery

-
 
2
.
 
R
e
-
e
n
a
b
l
e
 
p
r
o
v
i
d
e
r
s
/
m
e
m
b
e
r
s
h
i
p
s
 
o
n
l
y
 
a
f
t
e
r
 
v
e
r
i
f
i
c
a
t
i
o
n
.## Recovery

-
 
3
.
 
C
o
n
f
i
r
m
 
a
c
c
e
p
t
a
n
c
e
 
e
n
f
o
r
c
e
m
e
n
t
 
s
t
i
l
l
 
p
a
s
s
e
s
 
f
o
r
 
t
h
e
 
a
f
f
e
c
t
e
d
 
a
c
c
o
u
n
t
s
.## Recovery

-
 
4
.
 
V
e
r
i
f
y
 
a
 
f
u
l
l
 
s
m
o
k
e
 
(
a
u
t
h
,
 
j
o
b
s
,
 
k
e
y
w
o
r
d
s
)
 
b
e
f
o
r
e
 
r
e
s
t
o
r
i
n
g
 
c
u
s
t
o
m
e
r
 
a
c
c
e
s
s
.## Post Incident Review

-
 
1
.
 
R
e
c
o
r
d
 
t
h
e
 
i
n
c
i
d
e
n
t
:
 
t
i
m
e
l
i
n
e
,
 
r
o
o
t
 
c
a
u
s
e
,
 
a
c
t
i
o
n
s
,
 
e
v
i
d
e
n
c
e
 
p
a
t
h
s
,
 
a
n
d
 
o
u
t
c
o
m
e
.## Post Incident Review

-
 
2
.
 
I
d
e
n
t
i
f
y
 
c
o
n
t
r
o
l
 
g
a
p
s
 
a
n
d
 
u
p
d
a
t
e
 
t
h
e
 
r
i
s
k
 
r
e
g
i
s
t
e
r
 
+
 
k
n
o
w
n
 
g
a
p
s
.## Post Incident Review

-
 
3
.
 
U
p
d
a
t
e
 
t
h
i
s
 
r
u
n
b
o
o
k
 
i
f
 
t
h
e
 
i
n
c
i
d
e
n
t
 
r
e
v
e
a
l
e
d
 
a
 
m
i
s
s
i
n
g
 
s
t
e
p
.## Post Incident Review

-
 
4
.
 
R
e
-
r
u
n
 
t
h
e
 
a
f
f
e
c
t
e
d
 
t
e
s
t
 
s
u
r
f
a
c
e
 
(
a
u
t
h
o
r
i
z
a
t
i
o
n
,
 
f
i
n
a
n
c
i
a
l
 
i
n
t
e
g
r
i
t
y
,
 
b
e
t
a
 
a
c
c
e
p
t
a
n
c
e
)
.

Every step uses only the foundation API, the vault CLI, docker/psql for the local staging box, and SQL on the foundation DB — no undocumented tribal knowledge required.
