// Copyright Google Inc. All Rights Reserved.
(function() {
    /*

 Copyright The Closure Library Authors.
 SPDX-License-Identifier: Apache-2.0
*/
    var m, aa = function(a) {
        var b = 0;
        return function() {
            return b < a.length ? {
                done: !1,
                value: a[b++]
            } : {
                done: !0
            }
        }
    }, ba = "function" == typeof Object.defineProperties ? Object.defineProperty : function(a, b, c) {
        if (a == Array.prototype || a == Object.prototype)
            return a;
        a[b] = c.value;
        return a
    }
    , ca = function(a) {
        a = ["object" == typeof globalThis && globalThis, a, "object" == typeof window && window, "object" == typeof self && self, "object" == typeof global && global];
        for (var b = 0; b < a.length; ++b) {
            var c = a[b];
            if (c && c.Math == Math)
                return c
        }
        throw Error("Cannot find global object");
    }, p = ca(this), q = function(a, b) {
        if (b)
            a: {
                var c = p;
                a = a.split(".");
                for (var d = 0; d < a.length - 1; d++) {
                    var e = a[d];
                    if (!(e in c))
                        break a;
                    c = c[e]
                }
                a = a[a.length - 1];
                d = c[a];
                b = b(d);
                b != d && null != b && ba(c, a, {
                    configurable: !0,
                    writable: !0,
                    value: b
                })
            }
    };
    q("Symbol", function(a) {
        if (a)
            return a;
        var b = function(f, g) {
            this.$jscomp$symbol$id_ = f;
            ba(this, "description", {
                configurable: !0,
                writable: !0,
                value: g
            })
        };
        b.prototype.toString = function() {
            return this.$jscomp$symbol$id_
        }
        ;
        var c = "jscomp_symbol_" + (1E9 * Math.random() >>> 0) + "_"
          , d = 0
          , e = function(f) {
            if (this instanceof e)
                throw new TypeError("Symbol is not a constructor");
            return new b(c + (f || "") + "_" + d++,f)
        };
        return e
    });
    q("Symbol.iterator", function(a) {
        if (a)
            return a;
        a = Symbol("Symbol.iterator");
        for (var b = "Array Int8Array Uint8Array Uint8ClampedArray Int16Array Uint16Array Int32Array Uint32Array Float32Array Float64Array".split(" "), c = 0; c < b.length; c++) {
            var d = p[b[c]];
            "function" === typeof d && "function" != typeof d.prototype[a] && ba(d.prototype, a, {
                configurable: !0,
                writable: !0,
                value: function() {
                    return da(aa(this))
                }
            })
        }
        return a
    });
    var da = function(a) {
        a = {
            next: a
        };
        a[Symbol.iterator] = function() {
            return this
        }
        ;
        return a
    }
      , r = function(a) {
        var b = "undefined" != typeof Symbol && Symbol.iterator && a[Symbol.iterator];
        return b ? b.call(a) : {
            next: aa(a)
        }
    }
      , t = function(a, b) {
        return Object.prototype.hasOwnProperty.call(a, b)
    }
      , ea = "function" == typeof Object.assign ? Object.assign : function(a, b) {
        for (var c = 1; c < arguments.length; c++) {
            var d = arguments[c];
            if (d)
                for (var e in d)
                    t(d, e) && (a[e] = d[e])
        }
        return a
    }
    ;
    q("Object.assign", function(a) {
        return a || ea
    });
    var ha = "function" == typeof Object.create ? Object.create : function(a) {
        var b = function() {};
        b.prototype = a;
        return new b
    }
    , ia;
    if ("function" == typeof Object.setPrototypeOf)
        ia = Object.setPrototypeOf;
    else {
        var ja;
        a: {
            var ka = {
                a: !0
            }
              , la = {};
            try {
                la.__proto__ = ka;
                ja = la.a;
                break a
            } catch (a) {}
            ja = !1
        }
        ia = ja ? function(a, b) {
            a.__proto__ = b;
            if (a.__proto__ !== b)
                throw new TypeError(a + " is not extensible");
            return a
        }
        : null
    }
    var ma = ia
      , u = function(a, b) {
        a.prototype = ha(b.prototype);
        a.prototype.constructor = a;
        if (ma)
            ma(a, b);
        else
            for (var c in b)
                if ("prototype" != c)
                    if (Object.defineProperties) {
                        var d = Object.getOwnPropertyDescriptor(b, c);
                        d && Object.defineProperty(a, c, d)
                    } else
                        a[c] = b[c];
        a.superClass_ = b.prototype
    }
      , na = function() {
        this.isRunning_ = !1;
        this.yieldAllIterator_ = null;
        this.yieldResult = void 0;
        this.nextAddress = 1;
        this.finallyAddress_ = this.catchAddress_ = 0;
        this.abruptCompletion_ = null
    }
      , oa = function(a) {
        if (a.isRunning_)
            throw new TypeError("Generator is already running");
        a.isRunning_ = !0
    };
    na.prototype.next_ = function(a) {
        this.yieldResult = a
    }
    ;
    na.prototype.throw_ = function(a) {
        this.abruptCompletion_ = {
            exception: a,
            isException: !0
        };
        this.nextAddress = this.catchAddress_ || this.finallyAddress_
    }
    ;
    na.prototype.return = function(a) {
        this.abruptCompletion_ = {
            return: a
        };
        this.nextAddress = this.finallyAddress_
    }
    ;
    var pa = function(a, b, c) {
        a.nextAddress = c;
        return {
            value: b
        }
    }
      , ra = function() {
        var a = qa;
        this.object_ = a;
        this.properties_ = [];
        for (var b in a)
            this.properties_.push(b);
        this.properties_.reverse()
    }
      , sa = function(a) {
        this.context_ = new na;
        this.program_ = a
    };
    sa.prototype.next_ = function(a) {
        oa(this.context_);
        if (this.context_.yieldAllIterator_)
            return ua(this, this.context_.yieldAllIterator_.next, a, this.context_.next_);
        this.context_.next_(a);
        return va(this)
    }
    ;
    var wa = function(a, b) {
        oa(a.context_);
        var c = a.context_.yieldAllIterator_;
        if (c)
            return ua(a, "return"in c ? c["return"] : function(d) {
                return {
                    value: d,
                    done: !0
                }
            }
            , b, a.context_.return);
        a.context_.return(b);
        return va(a)
    };
    sa.prototype.throw_ = function(a) {
        oa(this.context_);
        if (this.context_.yieldAllIterator_)
            return ua(this, this.context_.yieldAllIterator_["throw"], a, this.context_.next_);
        this.context_.throw_(a);
        return va(this)
    }
    ;
    var ua = function(a, b, c, d) {
        try {
            var e = b.call(a.context_.yieldAllIterator_, c);
            if (!(e instanceof Object))
                throw new TypeError("Iterator result " + e + " is not an object");
            if (!e.done)
                return a.context_.isRunning_ = !1,
                e;
            var f = e.value
        } catch (g) {
            return a.context_.yieldAllIterator_ = null,
            a.context_.throw_(g),
            va(a)
        }
        a.context_.yieldAllIterator_ = null;
        d.call(a.context_, f);
        return va(a)
    }
      , va = function(a) {
        for (; a.context_.nextAddress; )
            try {
                var b = a.program_(a.context_);
                if (b)
                    return a.context_.isRunning_ = !1,
                    {
                        value: b.value,
                        done: !1
                    }
            } catch (c) {
                a.context_.yieldResult = void 0,
                a.context_.throw_(c)
            }
        a.context_.isRunning_ = !1;
        if (a.context_.abruptCompletion_) {
            b = a.context_.abruptCompletion_;
            a.context_.abruptCompletion_ = null;
            if (b.isException)
                throw b.exception;
            return {
                value: b.return,
                done: !0
            }
        }
        return {
            value: void 0,
            done: !0
        }
    }
      , xa = function(a) {
        this.next = function(b) {
            return a.next_(b)
        }
        ;
        this.throw = function(b) {
            return a.throw_(b)
        }
        ;
        this.return = function(b) {
            return wa(a, b)
        }
        ;
        this[Symbol.iterator] = function() {
            return this
        }
    }
      , ya = function(a) {
        function b(d) {
            return a.next(d)
        }
        function c(d) {
            return a.throw(d)
        }
        return new Promise(function(d, e) {
            function f(g) {
                g.done ? d(g.value) : Promise.resolve(g.value).then(b, c).then(f, e)
            }
            f(a.next())
        }
        )
    }
      , v = function(a) {
        return ya(new xa(new sa(a)))
    };
    q("Promise", function(a) {
        function b() {
            this.batch_ = null
        }
        function c(g) {
            return g instanceof e ? g : new e(function(h) {
                h(g)
            }
            )
        }
        if (a)
            return a;
        b.prototype.asyncExecute = function(g) {
            if (null == this.batch_) {
                this.batch_ = [];
                var h = this;
                this.asyncExecuteFunction(function() {
                    h.executeBatch_()
                })
            }
            this.batch_.push(g)
        }
        ;
        var d = p.setTimeout;
        b.prototype.asyncExecuteFunction = function(g) {
            d(g, 0)
        }
        ;
        b.prototype.executeBatch_ = function() {
            for (; this.batch_ && this.batch_.length; ) {
                var g = this.batch_;
                this.batch_ = [];
                for (var h = 0; h < g.length; ++h) {
                    var k = g[h];
                    g[h] = null;
                    try {
                        k()
                    } catch (l) {
                        this.asyncThrow_(l)
                    }
                }
            }
            this.batch_ = null
        }
        ;
        b.prototype.asyncThrow_ = function(g) {
            this.asyncExecuteFunction(function() {
                throw g;
            })
        }
        ;
        var e = function(g) {
            this.state_ = 0;
            this.result_ = void 0;
            this.onSettledCallbacks_ = [];
            this.isRejectionHandled_ = !1;
            var h = this.createResolveAndReject_();
            try {
                g(h.resolve, h.reject)
            } catch (k) {
                h.reject(k)
            }
        };
        e.prototype.createResolveAndReject_ = function() {
            function g(l) {
                return function(n) {
                    k || (k = !0,
                    l.call(h, n))
                }
            }
            var h = this
              , k = !1;
            return {
                resolve: g(this.resolveTo_),
                reject: g(this.reject_)
            }
        }
        ;
        e.prototype.resolveTo_ = function(g) {
            if (g === this)
                this.reject_(new TypeError("A Promise cannot resolve to itself"));
            else if (g instanceof e)
                this.settleSameAsPromise_(g);
            else {
                a: switch (typeof g) {
                case "object":
                    var h = null != g;
                    break a;
                case "function":
                    h = !0;
                    break a;
                default:
                    h = !1
                }
                h ? this.resolveToNonPromiseObj_(g) : this.fulfill_(g)
            }
        }
        ;
        e.prototype.resolveToNonPromiseObj_ = function(g) {
            var h = void 0;
            try {
                h = g.then
            } catch (k) {
                this.reject_(k);
                return
            }
            "function" == typeof h ? this.settleSameAsThenable_(h, g) : this.fulfill_(g)
        }
        ;
        e.prototype.reject_ = function(g) {
            this.settle_(2, g)
        }
        ;
        e.prototype.fulfill_ = function(g) {
            this.settle_(1, g)
        }
        ;
        e.prototype.settle_ = function(g, h) {
            if (0 != this.state_)
                throw Error("Cannot settle(" + g + ", " + h + "): Promise already settled in state" + this.state_);
            this.state_ = g;
            this.result_ = h;
            2 === this.state_ && this.scheduleUnhandledRejectionCheck_();
            this.executeOnSettledCallbacks_()
        }
        ;
        e.prototype.scheduleUnhandledRejectionCheck_ = function() {
            var g = this;
            d(function() {
                if (g.notifyUnhandledRejection_()) {
                    var h = p.console;
                    "undefined" !== typeof h && h.error(g.result_)
                }
            }, 1)
        }
        ;
        e.prototype.notifyUnhandledRejection_ = function() {
            if (this.isRejectionHandled_)
                return !1;
            var g = p.CustomEvent
              , h = p.Event
              , k = p.dispatchEvent;
            if ("undefined" === typeof k)
                return !0;
            "function" === typeof g ? g = new g("unhandledrejection",{
                cancelable: !0
            }) : "function" === typeof h ? g = new h("unhandledrejection",{
                cancelable: !0
            }) : (g = p.document.createEvent("CustomEvent"),
            g.initCustomEvent("unhandledrejection", !1, !0, g));
            g.promise = this;
            g.reason = this.result_;
            return k(g)
        }
        ;
        e.prototype.executeOnSettledCallbacks_ = function() {
            if (null != this.onSettledCallbacks_) {
                for (var g = 0; g < this.onSettledCallbacks_.length; ++g)
                    f.asyncExecute(this.onSettledCallbacks_[g]);
                this.onSettledCallbacks_ = null
            }
        }
        ;
        var f = new b;
        e.prototype.settleSameAsPromise_ = function(g) {
            var h = this.createResolveAndReject_();
            g.callWhenSettled_(h.resolve, h.reject)
        }
        ;
        e.prototype.settleSameAsThenable_ = function(g, h) {
            var k = this.createResolveAndReject_();
            try {
                g.call(h, k.resolve, k.reject)
            } catch (l) {
                k.reject(l)
            }
        }
        ;
        e.prototype.then = function(g, h) {
            function k(A, G) {
                return "function" == typeof A ? function(fa) {
                    try {
                        l(A(fa))
                    } catch (ta) {
                        n(ta)
                    }
                }
                : G
            }
            var l, n, y = new e(function(A, G) {
                l = A;
                n = G
            }
            );
            this.callWhenSettled_(k(g, l), k(h, n));
            return y
        }
        ;
        e.prototype.catch = function(g) {
            return this.then(void 0, g)
        }
        ;
        e.prototype.callWhenSettled_ = function(g, h) {
            function k() {
                switch (l.state_) {
                case 1:
                    g(l.result_);
                    break;
                case 2:
                    h(l.result_);
                    break;
                default:
                    throw Error("Unexpected state: " + l.state_);
                }
            }
            var l = this;
            null == this.onSettledCallbacks_ ? f.asyncExecute(k) : this.onSettledCallbacks_.push(k);
            this.isRejectionHandled_ = !0
        }
        ;
        e.resolve = c;
        e.reject = function(g) {
            return new e(function(h, k) {
                k(g)
            }
            )
        }
        ;
        e.race = function(g) {
            return new e(function(h, k) {
                for (var l = r(g), n = l.next(); !n.done; n = l.next())
                    c(n.value).callWhenSettled_(h, k)
            }
            )
        }
        ;
        e.all = function(g) {
            var h = r(g)
              , k = h.next();
            return k.done ? c([]) : new e(function(l, n) {
                function y(fa) {
                    return function(ta) {
                        A[fa] = ta;
                        G--;
                        0 == G && l(A)
                    }
                }
                var A = []
                  , G = 0;
                do
                    A.push(void 0),
                    G++,
                    c(k.value).callWhenSettled_(y(A.length - 1), n),
                    k = h.next();
                while (!k.done)
            }
            )
        }
        ;
        return e
    });
    q("WeakMap", function(a) {
        function b() {}
        function c(k) {
            var l = typeof k;
            return "object" === l && null !== k || "function" === l
        }
        function d(k) {
            if (!t(k, f)) {
                var l = new b;
                ba(k, f, {
                    value: l
                })
            }
        }
        function e(k) {
            var l = Object[k];
            l && (Object[k] = function(n) {
                if (n instanceof b)
                    return n;
                Object.isExtensible(n) && d(n);
                return l(n)
            }
            )
        }
        if (function() {
            if (!a || !Object.seal)
                return !1;
            try {
                var k = Object.seal({})
                  , l = Object.seal({})
                  , n = new a([[k, 2], [l, 3]]);
                if (2 != n.get(k) || 3 != n.get(l))
                    return !1;
                n.delete(k);
                n.set(l, 4);
                return !n.has(k) && 4 == n.get(l)
            } catch (y) {
                return !1
            }
        }())
            return a;
        var f = "$jscomp_hidden_" + Math.random();
        e("freeze");
        e("preventExtensions");
        e("seal");
        var g = 0
          , h = function(k) {
            this.id_ = (g += Math.random() + 1).toString();
            if (k) {
                k = r(k);
                for (var l; !(l = k.next()).done; )
                    l = l.value,
                    this.set(l[0], l[1])
            }
        };
        h.prototype.set = function(k, l) {
            if (!c(k))
                throw Error("Invalid WeakMap key");
            d(k);
            if (!t(k, f))
                throw Error("WeakMap key fail: " + k);
            k[f][this.id_] = l;
            return this
        }
        ;
        h.prototype.get = function(k) {
            return c(k) && t(k, f) ? k[f][this.id_] : void 0
        }
        ;
        h.prototype.has = function(k) {
            return c(k) && t(k, f) && t(k[f], this.id_)
        }
        ;
        h.prototype.delete = function(k) {
            return c(k) && t(k, f) && t(k[f], this.id_) ? delete k[f][this.id_] : !1
        }
        ;
        return h
    });
    q("Map", function(a) {
        if (function() {
            if (!a || "function" != typeof a || !a.prototype.entries || "function" != typeof Object.seal)
                return !1;
            try {
                var h = Object.seal({
                    x: 4
                })
                  , k = new a(r([[h, "s"]]));
                if ("s" != k.get(h) || 1 != k.size || k.get({
                    x: 4
                }) || k.set({
                    x: 4
                }, "t") != k || 2 != k.size)
                    return !1;
                var l = k.entries()
                  , n = l.next();
                if (n.done || n.value[0] != h || "s" != n.value[1])
                    return !1;
                n = l.next();
                return n.done || 4 != n.value[0].x || "t" != n.value[1] || !l.next().done ? !1 : !0
            } catch (y) {
                return !1
            }
        }())
            return a;
        var b = new WeakMap
          , c = function(h) {
            this.data_ = {};
            this.head_ = f();
            this.size = 0;
            if (h) {
                h = r(h);
                for (var k; !(k = h.next()).done; )
                    k = k.value,
                    this.set(k[0], k[1])
            }
        };
        c.prototype.set = function(h, k) {
            h = 0 === h ? 0 : h;
            var l = d(this, h);
            l.list || (l.list = this.data_[l.id] = []);
            l.entry ? l.entry.value = k : (l.entry = {
                next: this.head_,
                previous: this.head_.previous,
                head: this.head_,
                key: h,
                value: k
            },
            l.list.push(l.entry),
            this.head_.previous.next = l.entry,
            this.head_.previous = l.entry,
            this.size++);
            return this
        }
        ;
        c.prototype.delete = function(h) {
            h = d(this, h);
            return h.entry && h.list ? (h.list.splice(h.index, 1),
            h.list.length || delete this.data_[h.id],
            h.entry.previous.next = h.entry.next,
            h.entry.next.previous = h.entry.previous,
            h.entry.head = null,
            this.size--,
            !0) : !1
        }
        ;
        c.prototype.clear = function() {
            this.data_ = {};
            this.head_ = this.head_.previous = f();
            this.size = 0
        }
        ;
        c.prototype.has = function(h) {
            return !!d(this, h).entry
        }
        ;
        c.prototype.get = function(h) {
            return (h = d(this, h).entry) && h.value
        }
        ;
        c.prototype.entries = function() {
            return e(this, function(h) {
                return [h.key, h.value]
            })
        }
        ;
        c.prototype.keys = function() {
            return e(this, function(h) {
                return h.key
            })
        }
        ;
        c.prototype.values = function() {
            return e(this, function(h) {
                return h.value
            })
        }
        ;
        c.prototype.forEach = function(h, k) {
            for (var l = this.entries(), n; !(n = l.next()).done; )
                n = n.value,
                h.call(k, n[1], n[0], this)
        }
        ;
        c.prototype[Symbol.iterator] = c.prototype.entries;
        var d = function(h, k) {
            var l = k && typeof k;
            "object" == l || "function" == l ? b.has(k) ? l = b.get(k) : (l = "" + ++g,
            b.set(k, l)) : l = "p_" + k;
            var n = h.data_[l];
            if (n && t(h.data_, l))
                for (h = 0; h < n.length; h++) {
                    var y = n[h];
                    if (k !== k && y.key !== y.key || k === y.key)
                        return {
                            id: l,
                            list: n,
                            index: h,
                            entry: y
                        }
                }
            return {
                id: l,
                list: n,
                index: -1,
                entry: void 0
            }
        }
          , e = function(h, k) {
            var l = h.head_;
            return da(function() {
                if (l) {
                    for (; l.head != h.head_; )
                        l = l.previous;
                    for (; l.next != l.head; )
                        return l = l.next,
                        {
                            done: !1,
                            value: k(l)
                        };
                    l = null
                }
                return {
                    done: !0,
                    value: void 0
                }
            })
        }
          , f = function() {
            var h = {};
            return h.previous = h.next = h.head = h
        }
          , g = 0;
        return c
    });
    q("Array.prototype.find", function(a) {
        return a ? a : function(b, c) {
            a: {
                var d = this;
                d instanceof String && (d = String(d));
                for (var e = d.length, f = 0; f < e; f++) {
                    var g = d[f];
                    if (b.call(c, g, f, d)) {
                        b = g;
                        break a
                    }
                }
                b = void 0
            }
            return b
        }
    });
    var za = function(a, b) {
        a instanceof String && (a += "");
        var c = 0
          , d = !1
          , e = {
            next: function() {
                if (!d && c < a.length) {
                    var f = c++;
                    return {
                        value: b(f, a[f]),
                        done: !1
                    }
                }
                d = !0;
                return {
                    done: !0,
                    value: void 0
                }
            }
        };
        e[Symbol.iterator] = function() {
            return e
        }
        ;
        return e
    };
    q("Array.prototype.entries", function(a) {
        return a ? a : function() {
            return za(this, function(b, c) {
                return [b, c]
            })
        }
    });
    q("Object.entries", function(a) {
        return a ? a : function(b) {
            var c = [], d;
            for (d in b)
                t(b, d) && c.push([d, b[d]]);
            return c
        }
    });
    q("Object.is", function(a) {
        return a ? a : function(b, c) {
            return b === c ? 0 !== b || 1 / b === 1 / c : b !== b && c !== c
        }
    });
    q("Array.prototype.includes", function(a) {
        return a ? a : function(b, c) {
            var d = this;
            d instanceof String && (d = String(d));
            var e = d.length;
            c = c || 0;
            for (0 > c && (c = Math.max(c + e, 0)); c < e; c++) {
                var f = d[c];
                if (f === b || Object.is(f, b))
                    return !0
            }
            return !1
        }
    });
    q("String.prototype.includes", function(a) {
        return a ? a : function(b, c) {
            if (null == this)
                throw new TypeError("The 'this' value for String.prototype.includes must not be null or undefined");
            if (b instanceof RegExp)
                throw new TypeError("First argument to String.prototype.includes must not be a regular expression");
            return -1 !== (this + "").indexOf(b, c || 0)
        }
    });
    q("Set", function(a) {
        if (function() {
            if (!a || "function" != typeof a || !a.prototype.entries || "function" != typeof Object.seal)
                return !1;
            try {
                var c = Object.seal({
                    x: 4
                })
                  , d = new a(r([c]));
                if (!d.has(c) || 1 != d.size || d.add(c) != d || 1 != d.size || d.add({
                    x: 4
                }) != d || 2 != d.size)
                    return !1;
                var e = d.entries()
                  , f = e.next();
                if (f.done || f.value[0] != c || f.value[1] != c)
                    return !1;
                f = e.next();
                return f.done || f.value[0] == c || 4 != f.value[0].x || f.value[1] != f.value[0] ? !1 : e.next().done
            } catch (g) {
                return !1
            }
        }())
            return a;
        var b = function(c) {
            this.map_ = new Map;
            if (c) {
                c = r(c);
                for (var d; !(d = c.next()).done; )
                    this.add(d.value)
            }
            this.size = this.map_.size
        };
        b.prototype.add = function(c) {
            c = 0 === c ? 0 : c;
            this.map_.set(c, c);
            this.size = this.map_.size;
            return this
        }
        ;
        b.prototype.delete = function(c) {
            c = this.map_.delete(c);
            this.size = this.map_.size;
            return c
        }
        ;
        b.prototype.clear = function() {
            this.map_.clear();
            this.size = 0
        }
        ;
        b.prototype.has = function(c) {
            return this.map_.has(c)
        }
        ;
        b.prototype.entries = function() {
            return this.map_.entries()
        }
        ;
        b.prototype.values = function() {
            return this.map_.values()
        }
        ;
        b.prototype.keys = b.prototype.values;
        b.prototype[Symbol.iterator] = b.prototype.values;
        b.prototype.forEach = function(c, d) {
            var e = this;
            this.map_.forEach(function(f) {
                return c.call(d, f, f, e)
            })
        }
        ;
        return b
    });
    q("Promise.prototype.finally", function(a) {
        return a ? a : function(b) {
            return this.then(function(c) {
                return Promise.resolve(b()).then(function() {
                    return c
                })
            }, function(c) {
                return Promise.resolve(b()).then(function() {
                    throw c;
                })
            })
        }
    });
    var Aa = this || self
      , Ca = function(a) {
        var b = typeof a;
        return "object" == b && null != a || "function" == b
    }
      , Da = function(a, b, c) {
        return a.call.apply(a.bind, arguments)
    }
      , Ea = function(a, b, c) {
        if (!a)
            throw Error();
        if (2 < arguments.length) {
            var d = Array.prototype.slice.call(arguments, 2);
            return function() {
                var e = Array.prototype.slice.call(arguments);
                Array.prototype.unshift.apply(e, d);
                return a.apply(b, e)
            }
        }
        return function() {
            return a.apply(b, arguments)
        }
    }
      , Fa = function(a, b, c) {
        Fa = Function.prototype.bind && -1 != Function.prototype.bind.toString().indexOf("native code") ? Da : Ea;
        return Fa.apply(null, arguments)
    }
      , Ga = function(a, b) {
        var c = Array.prototype.slice.call(arguments, 1);
        return function() {
            var d = c.slice();
            d.push.apply(d, arguments);
            return a.apply(this, d)
        }
    }
      , w = function(a, b) {
        a = a.split(".");
        var c = Aa;
        a[0]in c || "undefined" == typeof c.execScript || c.execScript("var " + a[0]);
        for (var d; a.length && (d = a.shift()); )
            a.length || void 0 === b ? c = c[d] && c[d] !== Object.prototype[d] ? c[d] : c[d] = {} : c[d] = b
    }
      , Ha = function(a, b) {
        function c() {}
        c.prototype = b.prototype;
        a.superClass_ = b.prototype;
        a.prototype = new c;
        a.prototype.constructor = a;
        a.base = function(d, e, f) {
            for (var g = Array(arguments.length - 2), h = 2; h < arguments.length; h++)
                g[h - 2] = arguments[h];
            return b.prototype[e].apply(d, g)
        }
    };
    function Ia() {
        try {
            var a = cast.__platform__.channel;
            if (!a)
                throw new ReferenceError("Channel is not defined");
        } catch (b) {
            b instanceof ReferenceError && (a = aogh.channel)
        } finally {
            a || (console.error("Could not find platform channel."),
            console.error("Please re-run the application on a Google Home platform."))
        }
        return a
    }
    ;function Ja(a, b) {
        if (Error.captureStackTrace)
            Error.captureStackTrace(this, Ja);
        else {
            var c = Error().stack;
            c && (this.stack = c)
        }
        a && (this.message = String(a));
        void 0 !== b && (this.cause = b)
    }
    Ha(Ja, Error);
    Ja.prototype.name = "CustomError";
    function Ka(a, b) {
        a = a.split("%s");
        for (var c = "", d = a.length - 1, e = 0; e < d; e++)
            c += a[e] + (e < b.length ? b[e] : "%s");
        Ja.call(this, c + a[d])
    }
    Ha(Ka, Ja);
    Ka.prototype.name = "AssertionError";
    var x = function(a, b, c) {
        if (!a) {
            var d = "Assertion failed";
            if (b) {
                d += ": " + b;
                var e = Array.prototype.slice.call(arguments, 2)
            }
            throw new Ka("" + d,e || []);
        }
    }
      , La = function(a, b) {
        throw new Ka("Failure" + (a ? ": " + a : ""),Array.prototype.slice.call(arguments, 1));
    };
    function Ma(a) {
        a && "function" == typeof a.dispose && a.dispose()
    }
    ;var z = function() {
        this.disposed_ = this.disposed_;
        this.onDisposeCallbacks_ = this.onDisposeCallbacks_
    };
    z.prototype.disposed_ = !1;
    z.prototype.dispose = function() {
        this.disposed_ || (this.disposed_ = !0,
        this.disposeInternal())
    }
    ;
    var Na = function(a, b) {
        a.disposed_ ? b() : (a.onDisposeCallbacks_ || (a.onDisposeCallbacks_ = []),
        a.onDisposeCallbacks_.push(b))
    };
    z.prototype.disposeInternal = function() {
        if (this.onDisposeCallbacks_)
            for (; this.onDisposeCallbacks_.length; )
                this.onDisposeCallbacks_.shift()()
    }
    ;
    var B = function(a, b) {
        this.type = a;
        this.currentTarget = this.target = b;
        this.defaultPrevented = this.propagationStopped_ = !1
    };
    B.prototype.stopPropagation = function() {
        this.propagationStopped_ = !0
    }
    ;
    B.prototype.preventDefault = function() {
        this.defaultPrevented = !0
    }
    ;
    var Oa = Array.prototype.indexOf ? function(a, b) {
        x(null != a.length);
        return Array.prototype.indexOf.call(a, b, void 0)
    }
    : function(a, b) {
        if ("string" === typeof a)
            return "string" !== typeof b || 1 != b.length ? -1 : a.indexOf(b, 0);
        for (var c = 0; c < a.length; c++)
            if (c in a && a[c] === b)
                return c;
        return -1
    }
    ;
    var Pa = Object.freeze || function(a) {
        return a
    }
    ;
    var Qa = function() {
        if (!Aa.addEventListener || !Object.defineProperty)
            return !1;
        var a = !1
          , b = Object.defineProperty({}, "passive", {
            get: function() {
                a = !0
            }
        });
        try {
            Aa.addEventListener("test", function() {}, b),
            Aa.removeEventListener("test", function() {}, b)
        } catch (c) {}
        return a
    }();
    function Ra() {
        var a = Aa.navigator;
        return a && (a = a.userAgent) ? a : ""
    }
    ;var Sa = function(a) {
        Sa[" "](a);
        return a
    };
    Sa[" "] = function() {}
    ;
    var Ta = -1 != Ra().indexOf("Gecko") && !(-1 != Ra().toLowerCase().indexOf("webkit") && -1 == Ra().indexOf("Edge")) && !(-1 != Ra().indexOf("Trident") || -1 != Ra().indexOf("MSIE")) && -1 == Ra().indexOf("Edge")
      , Ua = -1 != Ra().toLowerCase().indexOf("webkit") && -1 == Ra().indexOf("Edge");
    var Wa = function(a, b) {
        B.call(this, a ? a.type : "");
        this.relatedTarget = this.currentTarget = this.target = null;
        this.button = this.screenY = this.screenX = this.clientY = this.clientX = this.offsetY = this.offsetX = 0;
        this.key = "";
        this.charCode = this.keyCode = 0;
        this.metaKey = this.shiftKey = this.altKey = this.ctrlKey = !1;
        this.state = null;
        this.pointerId = 0;
        this.pointerType = "";
        this.event_ = null;
        if (a) {
            var c = this.type = a.type
              , d = a.changedTouches && a.changedTouches.length ? a.changedTouches[0] : null;
            this.target = a.target || a.srcElement;
            this.currentTarget = b;
            if (b = a.relatedTarget) {
                if (Ta) {
                    a: {
                        try {
                            Sa(b.nodeName);
                            var e = !0;
                            break a
                        } catch (f) {}
                        e = !1
                    }
                    e || (b = null)
                }
            } else
                "mouseover" == c ? b = a.fromElement : "mouseout" == c && (b = a.toElement);
            this.relatedTarget = b;
            d ? (this.clientX = void 0 !== d.clientX ? d.clientX : d.pageX,
            this.clientY = void 0 !== d.clientY ? d.clientY : d.pageY,
            this.screenX = d.screenX || 0,
            this.screenY = d.screenY || 0) : (this.offsetX = Ua || void 0 !== a.offsetX ? a.offsetX : a.layerX,
            this.offsetY = Ua || void 0 !== a.offsetY ? a.offsetY : a.layerY,
            this.clientX = void 0 !== a.clientX ? a.clientX : a.pageX,
            this.clientY = void 0 !== a.clientY ? a.clientY : a.pageY,
            this.screenX = a.screenX || 0,
            this.screenY = a.screenY || 0);
            this.button = a.button;
            this.keyCode = a.keyCode || 0;
            this.key = a.key || "";
            this.charCode = a.charCode || ("keypress" == c ? a.keyCode : 0);
            this.ctrlKey = a.ctrlKey;
            this.altKey = a.altKey;
            this.shiftKey = a.shiftKey;
            this.metaKey = a.metaKey;
            this.pointerId = a.pointerId || 0;
            this.pointerType = "string" === typeof a.pointerType ? a.pointerType : Va[a.pointerType] || "";
            this.state = a.state;
            this.event_ = a;
            a.defaultPrevented && Wa.superClass_.preventDefault.call(this)
        }
    };
    Ha(Wa, B);
    var Va = Pa({
        2: "touch",
        3: "pen",
        4: "mouse"
    });
    Wa.prototype.stopPropagation = function() {
        Wa.superClass_.stopPropagation.call(this);
        this.event_.stopPropagation ? this.event_.stopPropagation() : this.event_.cancelBubble = !0
    }
    ;
    Wa.prototype.preventDefault = function() {
        Wa.superClass_.preventDefault.call(this);
        var a = this.event_;
        a.preventDefault ? a.preventDefault() : a.returnValue = !1
    }
    ;
    var Xa = "closure_listenable_" + (1E6 * Math.random() | 0);
    var Ya = 0;
    var Za = function(a, b, c, d, e) {
        this.listener = a;
        this.proxy = null;
        this.src = b;
        this.type = c;
        this.capture = !!d;
        this.handler = e;
        this.key = ++Ya;
        this.removed = this.callOnce = !1
    }
      , $a = function(a) {
        a.removed = !0;
        a.listener = null;
        a.proxy = null;
        a.src = null;
        a.handler = null
    };
    function ab(a, b) {
        for (var c in a)
            if (b.call(void 0, a[c], c, a))
                return !0;
        return !1
    }
    var bb = "constructor hasOwnProperty isPrototypeOf propertyIsEnumerable toLocaleString toString valueOf".split(" ");
    function cb(a, b) {
        for (var c, d, e = 1; e < arguments.length; e++) {
            d = arguments[e];
            for (c in d)
                a[c] = d[c];
            for (var f = 0; f < bb.length; f++)
                c = bb[f],
                Object.prototype.hasOwnProperty.call(d, c) && (a[c] = d[c])
        }
    }
    ;var db = function(a) {
        this.src = a;
        this.listeners = {};
        this.typeCount_ = 0
    };
    db.prototype.add = function(a, b, c, d, e) {
        var f = a.toString();
        a = this.listeners[f];
        a || (a = this.listeners[f] = [],
        this.typeCount_++);
        var g = eb(a, b, d, e);
        -1 < g ? (b = a[g],
        c || (b.callOnce = !1)) : (b = new Za(b,this.src,f,!!d,e),
        b.callOnce = c,
        a.push(b));
        return b
    }
    ;
    db.prototype.remove = function(a, b, c, d) {
        a = a.toString();
        if (!(a in this.listeners))
            return !1;
        var e = this.listeners[a];
        b = eb(e, b, c, d);
        return -1 < b ? ($a(e[b]),
        x(null != e.length),
        Array.prototype.splice.call(e, b, 1),
        0 == e.length && (delete this.listeners[a],
        this.typeCount_--),
        !0) : !1
    }
    ;
    var fb = function(a, b) {
        var c = b.type;
        if (c in a.listeners) {
            var d = a.listeners[c], e = Oa(d, b), f;
            if (f = 0 <= e)
                x(null != d.length),
                Array.prototype.splice.call(d, e, 1);
            f && ($a(b),
            0 == a.listeners[c].length && (delete a.listeners[c],
            a.typeCount_--))
        }
    };
    db.prototype.getListener = function(a, b, c, d) {
        a = this.listeners[a.toString()];
        var e = -1;
        a && (e = eb(a, b, c, d));
        return -1 < e ? a[e] : null
    }
    ;
    db.prototype.hasListener = function(a, b) {
        var c = void 0 !== a
          , d = c ? a.toString() : ""
          , e = void 0 !== b;
        return ab(this.listeners, function(f) {
            for (var g = 0; g < f.length; ++g)
                if (!(c && f[g].type != d || e && f[g].capture != b))
                    return !0;
            return !1
        })
    }
    ;
    var eb = function(a, b, c, d) {
        for (var e = 0; e < a.length; ++e) {
            var f = a[e];
            if (!f.removed && f.listener == b && f.capture == !!c && f.handler == d)
                return e
        }
        return -1
    };
    var gb = "closure_lm_" + (1E6 * Math.random() | 0)
      , hb = {}
      , ib = 0
      , kb = function(a, b, c, d, e) {
        if (d && d.once)
            jb(a, b, c, d, e);
        else if (Array.isArray(b))
            for (var f = 0; f < b.length; f++)
                kb(a, b[f], c, d, e);
        else
            c = lb(c),
            a && a[Xa] ? a.listen(b, c, Ca(d) ? !!d.capture : !!d, e) : mb(a, b, c, !1, d, e)
    }
      , mb = function(a, b, c, d, e, f) {
        if (!b)
            throw Error("Invalid event type");
        var g = Ca(e) ? !!e.capture : !!e
          , h = nb(a);
        h || (a[gb] = h = new db(a));
        c = h.add(b, c, d, g, f);
        if (!c.proxy) {
            d = ob();
            c.proxy = d;
            d.src = a;
            d.listener = c;
            if (a.addEventListener)
                Qa || (e = g),
                void 0 === e && (e = !1),
                a.addEventListener(b.toString(), d, e);
            else if (a.attachEvent)
                a.attachEvent(pb(b.toString()), d);
            else if (a.addListener && a.removeListener)
                x("change" === b, "MediaQueryList only has a change event"),
                a.addListener(d);
            else
                throw Error("addEventListener and attachEvent are unavailable.");
            ib++
        }
    }
      , ob = function() {
        var a = qb
          , b = function(c) {
            return a.call(b.src, b.listener, c)
        };
        return b
    }
      , jb = function(a, b, c, d, e) {
        if (Array.isArray(b))
            for (var f = 0; f < b.length; f++)
                jb(a, b[f], c, d, e);
        else
            c = lb(c),
            a && a[Xa] ? a.eventTargetListeners_.add(String(b), c, !0, Ca(d) ? !!d.capture : !!d, e) : mb(a, b, c, !0, d, e)
    }
      , rb = function(a, b, c, d, e) {
        if (Array.isArray(b))
            for (var f = 0; f < b.length; f++)
                rb(a, b[f], c, d, e);
        else
            d = Ca(d) ? !!d.capture : !!d,
            c = lb(c),
            a && a[Xa] ? a.eventTargetListeners_.remove(String(b), c, d, e) : a && (a = nb(a)) && (b = a.getListener(b, c, d, e)) && sb(b)
    }
      , sb = function(a) {
        if ("number" !== typeof a && a && !a.removed) {
            var b = a.src;
            if (b && b[Xa])
                fb(b.eventTargetListeners_, a);
            else {
                var c = a.type
                  , d = a.proxy;
                b.removeEventListener ? b.removeEventListener(c, d, a.capture) : b.detachEvent ? b.detachEvent(pb(c), d) : b.addListener && b.removeListener && b.removeListener(d);
                ib--;
                (c = nb(b)) ? (fb(c, a),
                0 == c.typeCount_ && (c.src = null,
                b[gb] = null)) : $a(a)
            }
        }
    }
      , pb = function(a) {
        return a in hb ? hb[a] : hb[a] = "on" + a
    }
      , qb = function(a, b) {
        if (a.removed)
            a = !0;
        else {
            b = new Wa(b,this);
            var c = a.listener
              , d = a.handler || a.src;
            a.callOnce && sb(a);
            a = c.call(d, b)
        }
        return a
    }
      , nb = function(a) {
        a = a[gb];
        return a instanceof db ? a : null
    }
      , tb = "__closure_events_fn_" + (1E9 * Math.random() >>> 0)
      , lb = function(a) {
        x(a, "Listener can not be null.");
        if ("function" === typeof a)
            return a;
        x(a.handleEvent, "An object listener must have handleEvent method.");
        a[tb] || (a[tb] = function(b) {
            return a.handleEvent(b)
        }
        );
        return a[tb]
    };
    var C = function() {
        z.call(this);
        this.eventTargetListeners_ = new db(this);
        this.actualEventTarget_ = this;
        this.parentEventTarget_ = null
    };
    Ha(C, z);
    C.prototype[Xa] = !0;
    m = C.prototype;
    m.addEventListener = function(a, b, c, d) {
        kb(this, a, b, c, d)
    }
    ;
    m.removeEventListener = function(a, b, c, d) {
        rb(this, a, b, c, d)
    }
    ;
    m.dispatchEvent = function(a) {
        ub(this);
        var b = this.parentEventTarget_;
        if (b) {
            var c = [];
            for (var d = 1; b; b = b.parentEventTarget_)
                c.push(b),
                x(1E3 > ++d, "infinite loop")
        }
        b = this.actualEventTarget_;
        d = a.type || a;
        if ("string" === typeof a)
            a = new B(a,b);
        else if (a instanceof B)
            a.target = a.target || b;
        else {
            var e = a;
            a = new B(d,b);
            cb(a, e)
        }
        e = !0;
        if (c)
            for (var f = c.length - 1; !a.propagationStopped_ && 0 <= f; f--) {
                var g = a.currentTarget = c[f];
                e = vb(g, d, !0, a) && e
            }
        a.propagationStopped_ || (g = a.currentTarget = b,
        e = vb(g, d, !0, a) && e,
        a.propagationStopped_ || (e = vb(g, d, !1, a) && e));
        if (c)
            for (f = 0; !a.propagationStopped_ && f < c.length; f++)
                g = a.currentTarget = c[f],
                e = vb(g, d, !1, a) && e;
        return e
    }
    ;
    m.disposeInternal = function() {
        C.superClass_.disposeInternal.call(this);
        if (this.eventTargetListeners_) {
            var a = this.eventTargetListeners_, b = 0, c;
            for (c in a.listeners) {
                for (var d = a.listeners[c], e = 0; e < d.length; e++)
                    ++b,
                    $a(d[e]);
                delete a.listeners[c];
                a.typeCount_--
            }
        }
        this.parentEventTarget_ = null
    }
    ;
    m.listen = function(a, b, c, d) {
        ub(this);
        return this.eventTargetListeners_.add(String(a), b, !1, c, d)
    }
    ;
    var vb = function(a, b, c, d) {
        b = a.eventTargetListeners_.listeners[String(b)];
        if (!b)
            return !0;
        b = b.concat();
        for (var e = !0, f = 0; f < b.length; ++f) {
            var g = b[f];
            if (g && !g.removed && g.capture == c) {
                var h = g.listener
                  , k = g.handler || g.src;
                g.callOnce && fb(a.eventTargetListeners_, g);
                e = !1 !== h.call(k, d) && e
            }
        }
        return e && !d.defaultPrevented
    };
    C.prototype.getListener = function(a, b, c, d) {
        return this.eventTargetListeners_.getListener(String(a), b, c, d)
    }
    ;
    C.prototype.hasListener = function(a, b) {
        return this.eventTargetListeners_.hasListener(void 0 !== a ? String(a) : void 0, b)
    }
    ;
    var ub = function(a) {
        x(a.eventTargetListeners_, "Event target is not initialized. Did you call the superclass (goog.events.EventTarget) constructor?")
    };
    var wb = function(a, b) {
        this.name = a;
        this.value = b
    };
    wb.prototype.toString = function() {
        return this.name
    }
    ;
    var xb = new wb("OFF",Infinity), yb = new wb("SEVERE",1E3), D = new wb("WARNING",900), zb = new wb("INFO",800), Ab = new wb("CONFIG",700), Bb = new wb("FINE",500), Cb = function() {
        this.capacity_ = 0;
        this.clear()
    }, Db;
    Cb.prototype.clear = function() {
        this.buffer_ = Array(this.capacity_);
        this.curIndex_ = -1;
        this.isFull_ = !1
    }
    ;
    var Eb = function(a, b, c) {
        this.exception_ = void 0;
        this.reset(a || xb, b, c, void 0, void 0)
    };
    Eb.prototype.reset = function(a, b, c, d) {
        this.time_ = d || Date.now();
        this.level_ = a;
        this.msg_ = b;
        this.loggerName_ = c;
        this.exception_ = void 0
    }
    ;
    var Fb = function(a, b) {
        this.level = null;
        this.handlers = [];
        this.parent = (void 0 === b ? null : b) || null;
        this.children = [];
        this.logger = {
            getName: function() {
                return a
            }
        }
    }, Gb = function(a) {
        if (a.level)
            return a.level;
        if (a.parent)
            return Gb(a.parent);
        La("Root logger has no level set.");
        return xb
    }, Hb = function(a, b) {
        for (; a; )
            a.handlers.forEach(function(c) {
                c(b)
            }),
            a = a.parent
    }, Ib = function() {
        this.entries = {};
        var a = new Fb("");
        a.level = Ab;
        this.entries[""] = a
    }, Jb, Kb = function(a, b, c) {
        var d = a.entries[b];
        if (d)
            return void 0 !== c && (d.level = c),
            d;
        d = Kb(a, b.slice(0, Math.max(b.lastIndexOf("."), 0)));
        var e = new Fb(b,d);
        a.entries[b] = e;
        d.children.push(e);
        void 0 !== c && (e.level = c);
        return e
    }, Lb = function() {
        Jb || (Jb = new Ib);
        return Jb
    }, E = function(a, b) {
        return Kb(Lb(), a, b).logger
    }, Mb = function(a, b, c, d) {
        var e;
        if (e = a)
            if (e = a && b) {
                e = b.value;
                var f = a ? Gb(Kb(Lb(), a.getName())) : xb;
                e = e >= f.value
            }
        if (e) {
            b = b || xb;
            e = Kb(Lb(), a.getName());
            "function" === typeof c && (c = c());
            Db || (Db = new Cb);
            f = Db;
            a = a.getName();
            if (0 < f.capacity_) {
                var g = (f.curIndex_ + 1) % f.capacity_;
                f.curIndex_ = g;
                f.isFull_ ? (f = f.buffer_[g],
                f.reset(b, c, a),
                a = f) : (f.isFull_ = g == f.capacity_ - 1,
                a = f.buffer_[g] = new Eb(b,c,a))
            } else
                a = new Eb(b,c,a);
            a.exception_ = d;
            Hb(e, a)
        }
    }, F = function(a, b, c) {
        a && Mb(a, yb, b, c)
    }, H = function(a, b) {
        a && Mb(a, D, b)
    }, I = function(a, b, c) {
        a && Mb(a, zb, b, c)
    };
    E("goog.net.WebSocket");
    var Nb = function(a) {
        B.call(this, "c");
        this.message = a
    };
    Ha(Nb, B);
    var Ob = E("sdk.common.platform.WebSocket"), Pb, Qb = function() {
        z.call(this);
        this.eventTarget_ = new C;
        this.opened_ = !1;
        Pb = Ia()
    };
    u(Qb, z);
    m = Qb.prototype;
    m.disposeInternal = function() {
        this.close();
        this.eventTarget_.dispose()
    }
    ;
    m.open = function() {
        var a = this;
        this.opened_ ? F(Ob, "PlatformChannel Already open") : Pb.open(function(b) {
            return a.onOpened_(b)
        }, function(b) {
            return a.onMessage_(b)
        })
    }
    ;
    m.close = function() {
        var a = this;
        this.opened_ ? Pb.close(function() {
            return a.onClosed_()
        }) : F(Ob, "PlatformChannel Cannot close unopened channel")
    }
    ;
    m.isOpen = function() {
        return this.opened_
    }
    ;
    m.send = function(a) {
        x(this.opened_, "Cannot send until channel is openned");
        Pb.send(a)
    }
    ;
    m.onOpened_ = function(a) {
        this.opened_ = a;
        this.dispatchEvent_(a ? "d" : "b")
    }
    ;
    m.onClosed_ = function() {
        this.opened_ && (this.opened_ = !1,
        this.dispatchEvent_("a"))
    }
    ;
    m.onMessage_ = function(a) {
        this.dispatchEvent_(new Nb(a))
    }
    ;
    m.addEventListener = function(a, b) {
        this.eventTarget_.listen(a, b)
    }
    ;
    m.removeEventListener = function(a, b) {
        this.eventTarget_.eventTargetListeners_.remove(String(a), b, void 0, void 0)
    }
    ;
    m.dispatchEvent_ = function(a) {
        a = "string" === typeof a ? new B(a) : a;
        a.target = this;
        this.eventTarget_.dispatchEvent(a)
    }
    ;
    var J = E("sdk.common.ipc", D)
      , Rb = function() {
        this.sendAsIs_ = !0;
        this.websocket_ = null;
        if (Ia()) {
            I(J, "IpcChannelUsing platform socket");
            var a = new Qb;
            this.websocket_ && this.websocket_.dispose();
            this.websocket_ = a;
            this.websocket_.addEventListener("d", this.onOpened_.bind(this));
            this.websocket_.addEventListener("a", this.onClosed_.bind(this));
            this.websocket_.addEventListener("b", this.onError_.bind(this));
            this.websocket_.addEventListener("c", this.onMessage_.bind(this))
        } else
            I(J, "IpcChannelCould not initiate connection to platform");
        this.eventTarget_ = new C
    };
    m = Rb.prototype;
    m.onOpened_ = function() {}
    ;
    m.onClosed_ = function() {}
    ;
    m.onError_ = function() {
        F(J, "IpcChannel Communication error")
    }
    ;
    m.onMessage_ = function(a) {
        I(J, "IpcChannelReceived message: " + a.message);
        try {
            var b = JSON.parse(a.message)
              , c = b.namespace
              , d = b.senderId
              , e = b.data;
            var f = c && d && e ? new Sb(c,d,e) : new Sb("urn:x-cast:com.google.cast.generic","*:*",a.message)
        } catch (g) {
            I(J, "IpcChannelParse error for packet: " + a.message),
            f = new Sb("urn:x-cast:com.google.cast.generic","*:*",a.message)
        }
        this.dispatchEvent_(f)
    }
    ;
    m.open = function() {
        J && Mb(J, Bb, "IpcChannelOpening message bus socket");
        this.websocket_.open("ws://localhost")
    }
    ;
    m.close = function() {
        I(J, "IpcChannelClosing message bus websocket");
        this.websocket_.close()
    }
    ;
    m.isOpen = function() {
        return this.websocket_.isOpen()
    }
    ;
    m.send = function(a, b, c) {
        a = this.sendAsIs_ ? c : JSON.stringify({
            namespace: a,
            senderId: b,
            data: c
        });
        this.websocket_.send(a);
        I(J, "IpcChannelMessage sent: " + a)
    }
    ;
    m.addEventListener = function(a, b) {
        this.eventTarget_.listen(a, b)
    }
    ;
    m.removeEventListener = function(a, b) {
        this.eventTarget_.eventTargetListeners_.remove(String(a), b, void 0, void 0)
    }
    ;
    m.dispatchEvent_ = function(a) {
        a.target = this;
        this.eventTarget_.dispatchEvent(a)
    }
    ;
    var Sb = function(a, b, c) {
        B.call(this, a);
        this.senderId = b;
        this.data = c
    };
    u(Sb, B);
    var Tb = E("sdk.common.messageBus", D)
      , Vb = function(a, b, c, d) {
        d = void 0 === d ? "STRING" : d;
        z.call(this);
        this.namespace_ = a;
        this.senderId_ = b;
        this.ipcChannel_ = c;
        this.messageType_ = d;
        this.onSend = this.onMessage = null;
        this.serializeMessage = this.defaultSerializeMessage_;
        this.deserializeMessage = this.defaultDeserializeMessage_;
        this.messageInternalHandler_ = this.onMessageInternal_.bind(this);
        this.ipcChannel_.addEventListener(this.namespace_, this.messageInternalHandler_)
    };
    u(Vb, z);
    var Wb = function(a) {
        return "MessageBus[" + a.namespace_ + "]"
    };
    Vb.prototype.onMessageInternal_ = function(a) {
        var b = this;
        Tb && Mb(Tb, Bb, Wb(this) + "Dispatching message");
        var c = "STRING" === this.messageType_ ? a.data : this.deserializeMessage(a.data)
          , d = new Xb("message",a.senderId,c);
        this.onMessage && setTimeout(function() {
            return b.onMessage(d)
        }, 0);
        this.eventTarget_ && (this.dispatchEvent_(new Xb(a.senderId,a.senderId,c)),
        this.dispatchEvent_(d))
    }
    ;
    var Yb = function(a, b) {
        a.ipcChannel_ && a.ipcChannel_.isOpen() || H(Tb, Wb(a) + "Application should not send requests before the system is ready (they will be ignored)");
        if (!a.onSend || !a.onSend(a.senderId_, a.namespace_, b))
            if ("STRING" === a.messageType_) {
                if ("string" != typeof b)
                    throw Error("Wrong argument, MessageBus type is STRING");
                a.ipcChannel_.send(a.namespace_, a.senderId_, b)
            } else
                a.ipcChannel_.send(a.namespace_, a.senderId_, a.serializeMessage(b))
    };
    m = Vb.prototype;
    m.send = function(a) {
        Yb(this, a)
    }
    ;
    m.sendLogs = function(a) {
        Yb(this, a)
    }
    ;
    m.defaultSerializeMessage_ = function(a) {
        if ("JSON" !== this.messageType_)
            throw Error("Unexpected message type for JSON serialization,please override serializeMessage");
        return JSON.stringify(a)
    }
    ;
    m.defaultDeserializeMessage_ = function(a) {
        if ("JSON" !== this.messageType_)
            throw Error("Unexpected message type for JSON serialization,please override deserializeMessage");
        return JSON.parse(a)
    }
    ;
    m.disposeInternal = function() {
        z.prototype.disposeInternal.call(this);
        this.ipcChannel_.removeEventListener(this.namespace_, this.messageInternalHandler_);
        this.eventTarget_.dispose();
        Tb && Mb(Tb, Bb, "Disposed " + Wb(this))
    }
    ;
    m.addEventListener = function(a, b) {
        this.eventTarget_ || (this.eventTarget_ = new C);
        this.eventTarget_.listen(a, b)
    }
    ;
    m.removeEventListener = function(a, b) {
        this.eventTarget_ || (this.eventTarget_ = new C);
        this.eventTarget_.eventTargetListeners_.remove(String(a), b, void 0, void 0)
    }
    ;
    m.dispatchEvent_ = function(a) {
        a.target = this;
        this.eventTarget_.dispatchEvent(a)
    }
    ;
    var Xb = function(a, b, c) {
        B.call(this, a);
        this.senderId = b;
        this.data = c
    };
    u(Xb, B);
    var Zb = function(a) {
        this.type = a
    }
      , $b = function() {
        this.type = "library.platform.APPLICATION_READY"
    };
    u($b, Zb);
    var K = function(a) {
        this.type = "platform.library.ACTION_START";
        this.intent = a
    };
    u(K, Zb);
    var ac = function(a) {
        this.type = a
    };
    u(ac, Zb);
    var bc = function(a) {
        this.type = a
    };
    u(bc, ac);
    var cc = function() {
        this.type = "library.platform.ACTION_SUCCESS"
    };
    u(cc, bc);
    var dc = function() {
        this.type = "library.platform.ACTION_PENDING"
    };
    u(dc, bc);
    var ec = function(a, b) {
        this.type = "library.platform.ACTION_FAILURE";
        this.errorCode = a;
        this.debugString = b
    };
    u(ec, bc);
    var fc = function(a) {
        var b = Error.call(this);
        this.message = b.message;
        "stack"in b && (this.stack = b.stack);
        this.errorCode = a || "GENERIC_ERROR";
        this.name = "ActionError"
    };
    u(fc, Error);
    var gc = {
        DISCONNECT: "action.devices.DISCONNECT",
        EVENT: "action.devices.EVENT",
        EXECUTE: "action.devices.EXECUTE",
        QUERY: "action.devices.QUERY",
        SYNC: "action.devices.SYNC",
        IDENTIFY: "action.devices.IDENTIFY",
        INDICATE: "action.devices.INDICATE",
        PARSE_NOTIFICATION: "action.devices.PARSE_NOTIFICATION",
        PROVISION: "action.devices.PROVISION",
        PROXY_SELECTED: "action.devices.PROXY_SELECTED",
        REACHABLE_DEVICES: "action.devices.REACHABLE_DEVICES",
        REGISTER: "action.devices.REGISTER",
        UPDATE: "action.devices.UPDATE",
        UNPROVISION: "action.devices.UNPROVISION",
        CLOUD_INTENT: "action.devices.CLOUD_INTENT",
        NOTIFICATION: "action.devices.NOTIFICATION",
        REPORT_STATE: "action.devices.REPORT_STATE",
        LOCAL_INTENT: "action.devices.LOCAL_INTENT"
    };
    w("smarthome.Intents", gc);
    var hc = {
        CLOUD_INTENT: "action.devices.CLOUD_INTENT",
        EVENT: "action.devices.EVENT",
        IDENTIFY: "action.devices.IDENTIFY",
        INDICATE: "action.devices.INDICATE",
        LOCAL_INTENT: "action.devices.LOCAL_INTENT",
        NOTIFICATION: "action.devices.NOTIFICATION",
        PROVISION: "action.devices.PROVISION",
        PROXY_SELECTED: "action.devices.PROXY_SELECTED",
        QUERY: "action.devices.QUERY",
        REACHABLE_DEVICES: "action.devices.REACHABLE_DEVICES",
        REGISTER: "action.devices.REGISTER",
        REPORT_STATE: "action.devices.REPORT_STATE",
        UNPROVISION: "action.devices.UNPROVISION",
        UPDATE: "action.devices.UPDATE",
        VERIFY: "action.devices.VERIFY",
        EXECUTE: "action.devices.EXECUTE",
        PARSE_NOTIFICATION: "action.devices.PARSE_NOTIFICATION"
    };
    var ic = function(a, b) {
        this.deviceManager_ = a;
        this.messageBus_ = b;
        this.requestIdToLogEntriesMap_ = new Map
    }
      , jc = function(a, b) {
        var c = b.requestId
          , d = a.requestIdToLogEntriesMap_.get(c) || [];
        d.push(b);
        a.requestIdToLogEntriesMap_.set(c, d)
    };
    ic.prototype.sendLogs = function(a) {
        var b = this
          , c = (this.requestIdToLogEntriesMap_.get(a.requestId) || []).map(function(e) {
            var f = e.timestamp
              , g = e.errorCode
              , h = e.severity;
            e = {
                requestId: e.requestId,
                timestamp: {
                    seconds: Math.floor(f / 1E3),
                    nanos: f % 1E3 * 1E6
                },
                appVersion: b.deviceManager_.appVersion_ || "unknownVersion",
                message: e.message,
                intent: gc[kc(a)],
                severity: h
            };
            g && (e.errorCode = g);
            return e
        });
        this.requestIdToLogEntriesMap_.delete(a.requestId);
        if (c.length) {
            var d = {
                requestId: a.requestId,
                type: "library.platform.LOG",
                logEntries: c
            };
            I(lc, "Sending custom logs to stackdriver: " + JSON.stringify(c));
            this.messageBus_.sendLogs(d)
        }
    }
    ;
    ic.prototype.info = function(a) {
        a && a.requestId ? jc(this, {
            requestId: a.requestId,
            message: a.message,
            timestamp: Date.now(),
            severity: "INFO"
        }) : H(lc, "logEntry or requestId missing in logEntry, message ignored.")
    }
    ;
    ic.prototype.error = function(a) {
        a && a.requestId ? jc(this, {
            requestId: a.requestId,
            message: a.message,
            errorCode: a.errorCode,
            timestamp: Date.now(),
            severity: "ERROR"
        }) : H(lc, "logEntry or requestId missing in logEntry, message ignored.")
    }
    ;
    ic.prototype.error = ic.prototype.error;
    ic.prototype.info = ic.prototype.info;
    var lc = E("smarthome.CommandManager", D);
    w("smarthome.Constants.EventType", {
        AUTOCONNECT: "AUTOCONNECT",
        DISCONNECT: "DISCONNECT"
    });
    w("smarthome.Constants.Protocol", {
        ASSISTANT: "ASSISTANT",
        BLE: "BLE",
        HTTP: "HTTP",
        SSID: "SSID",
        TCP: "TCP",
        UDP: "UDP",
        BLE_MESH: "BLE_MESH"
    });
    w("smarthome.Constants.RadioType", {
        BLE: "BLE",
        WIFI: "WiFi"
    });
    w("smarthome.Constants.BleOperation", {
        CONNECT: "CONNECT",
        CREATE_BOND: "CREATE_BOND",
        DISCONNECT: "DISCONNECT",
        GET_MTU: "GET_MTU",
        READ: "READ",
        REGISTER_FOR_NOTIFICATIONS: "REGISTER_FOR_NOTIFICATIONS",
        REMOVE_BOND: "REMOVE_BOND",
        REQUEST_MTU: "REQUEST_MTU",
        WRITE: "WRITE",
        WRITE_WITHOUT_RESPONSE: "WRITE_WITHOUT_RESPONSE"
    });
    w("smarthome.Constants.HttpOperation", {
        GET: "GET",
        POST: "POST",
        PUT: "PUT"
    });
    w("smarthome.Constants.SsidOperation", {
        CONNECT: "CONNECT",
        DISCONNECT: "DISCONNECT"
    });
    w("smarthome.Constants.TcpOperation", {
        READ: "READ",
        WRITE: "WRITE"
    });
    var mc = Math.floor(1E4 * Math.random())
      , L = function(a, b) {
        this.type = a;
        this.deviceId = "";
        this.commandId_ = mc++;
        this.protocol = b
    };
    L.prototype.toJSON = function() {
        return {
            requestId: this.requestId,
            type: this.type,
            commandId: this.commandId,
            deviceId: this.deviceId,
            protocol: this.protocol
        }
    }
    ;
    p.Object.defineProperties(L.prototype, {
        commandId: {
            configurable: !0,
            enumerable: !0,
            get: function() {
                return this.commandId_
            },
            set: function(a) {
                this.commandId_ = a
            }
        }
    });
    var nc = function(a, b) {
        L.call(this, a, b)
    };
    u(nc, L);
    nc.prototype.toJSON = function() {
        var a = L.prototype.toJSON.call(this);
        a.errorCode = this.errorCode;
        a.debugString = this.debugString;
        return a
    }
    ;
    var M = function(a, b, c) {
        c = void 0 === c ? "NONE" : c;
        L.call(this, "library.platform.COMMAND", a);
        this.data = "";
        this.dataEncoding = c;
        this.optionsKey_ = b
    };
    u(M, L);
    M.prototype.toJSON = function() {
        var a = L.prototype.toJSON.call(this);
        a.bytes = this.data;
        a[this.optionsKey_] = this.optionsValue_;
        this.template && (a.template = this.template);
        return a
    }
    ;
    var oc = function() {
        M.call(this, "HTTP", "httpOptions", "JSON");
        this.isSecure = !1;
        this.path = "";
        this.port = 80;
        this.dataType = this.headers = ""
    };
    u(oc, M);
    var pc = function(a) {
        return Object.entries(a).map(function(b) {
            var c = r(b);
            b = c.next().value;
            c = c.next().value;
            return b + ": " + c
        }).join("\r\n")
    };
    oc.prototype.toJSON = function() {
        var a = this.isSecure ? "HTTPS" : "HTTP"
          , b = this.additionalHeaders ? pc(this.additionalHeaders) : this.headers;
        this.optionsValue_ = {
            method: this.method,
            path: this.path,
            port: this.port,
            protocol: a,
            headers: b,
            dataType: this.dataType
        };
        return M.prototype.toJSON.call(this)
    }
    ;
    var qc = function() {
        M.call(this, "UDP", "udpOptions", "HEX_UPPERCASE")
    };
    u(qc, M);
    qc.prototype.toJSON = function() {
        this.optionsValue_ = {
            port: this.port,
            expectedResponsePackets: this.expectedResponsePackets
        };
        return M.prototype.toJSON.call(this)
    }
    ;
    var rc = function() {
        M.call(this, "TCP", "tcpOptions", "HEX_UPPERCASE");
        this.isSecure = !1
    };
    u(rc, M);
    rc.prototype.toJSON = function() {
        var a = this.isSecure ? "SECURE" : "INSECURE";
        if (this.isSecure && "EC-JPAKE" === this.cipher) {
            if (!this.shortCode)
                throw Error("shortCode is required with " + this.cipher);
            a = "TLS_ECJPAKE"
        }
        this.optionsValue_ = {
            security: a,
            port: this.port,
            operation: this.operation,
            hostname: this.hostname,
            bytesToRead: this.bytesToRead ? this.bytesToRead : 0
        };
        this.template && (this.optionsValue_.payloadTemplate = this.template);
        this.shortCode && (this.optionsValue_.shortCode = this.shortCode);
        return M.prototype.toJSON.call(this)
    }
    ;
    var sc = function() {
        M.call(this, "ASSISTANT", "assistantOptions", "BASE_64_RFC_4648")
    };
    u(sc, M);
    sc.prototype.toJSON = function() {
        this.optionsValue_ = {
            data: this.data
        };
        return M.prototype.toJSON.call(this)
    }
    ;
    var tc = function() {
        M.call(this, "BLE", "bleOptions", "HEX_UPPERCASE")
    };
    u(tc, M);
    tc.prototype.toJSON = function() {
        this.optionsValue_ = {
            serviceUuid: this.serviceUuid,
            characteristicUuid: this.characteristicUuid,
            operation: this.operation
        };
        this.mtu && (this.optionsValue_.mtu = this.mtu);
        return M.prototype.toJSON.call(this)
    }
    ;
    var uc = function() {
        M.call(this, "BLE_MESH", "bleMeshOptions", "HEX_UPPERCASE")
    };
    u(uc, M);
    uc.prototype.toJSON = function() {
        this.optionsValue_ = {
            opcode: this.opcode,
            parameters: this.parameters
        };
        return M.prototype.toJSON.call(this)
    }
    ;
    var vc = function() {
        M.call(this, "SSID", "ssidOptions")
    };
    u(vc, M);
    vc.prototype.toJSON = function() {
        this.optionsValue_ = {
            operation: this.operation
        };
        return M.prototype.toJSON.call(this)
    }
    ;
    var wc = function(a) {
        L.call(this, "platform.library.COMMAND_SUCCESS", a)
    };
    u(wc, L);
    var xc = function() {
        wc.call(this, "BLE")
    };
    u(xc, wc);
    var yc = function(a) {
        L.call(this, "platform.library.COMMAND_FAILURE", a)
    };
    u(yc, nc);
    w("smarthome.DataFlow.AssistantRequestData", sc);
    w("smarthome.DataFlow.BleMeshRequestData", uc);
    w("smarthome.DataFlow.BleRequestData", tc);
    w("smarthome.DataFlow.HttpRequestData", oc);
    w("smarthome.DataFlow.SsidRequestData", vc);
    w("smarthome.DataFlow.TcpRequestData", rc);
    w("smarthome.DataFlow.UdpRequestData", qc);
    var zc = "bleScanData codeScanData mdnsScanData ssidScanData udpScanData upnpScanData".split(" ");
    function Ac(a) {
        var b = a;
        if ("string" === typeof a)
            try {
                b = JSON.parse(a)
            } catch (c) {
                console.log("Error parsing " + a),
                console.error(c)
            }
        return b
    }
    function Bc(a, b) {
        if (b) {
            var c = b.verificationId;
            b = b.id;
            if (!c || !Array.isArray(a))
                return b;
            if (a = a.find(function(d) {
                return Array.isArray(d.otherDeviceIds) ? d.otherDeviceIds.includes(c) : !1
            }))
                return a.id
        }
    }
    function Cc(a) {
        var b = a.serviceName || ""
          , c = a.texts || []
          , d = {};
        try {
            var e = a.serviceName.split(".")
              , f = e[0]
              , g = e[1].substring(1)
              , h = e[2].substring(1);
            c.forEach(function(k) {
                k = k.split("=");
                d[k[0]] = k[1]
            });
            return {
                serviceName: b,
                name: f,
                type: g,
                protocol: h,
                data: c,
                txt: d
            }
        } catch (k) {
            throw console.error("Failed to parse mDNS scan data " + a),
            k;
        }
    }
    function Dc(a) {
        var b = []
          , c = function(f) {
            f.customData && (f.customData = Ac(f.customData));
            return f
        }
          , d = RegExp("fakehubfor-")
          , e = function(f) {
            return !d.test(f.id)
        };
        (Array.isArray(a.devices) ? a.devices.map(c).filter(e) : []).forEach(function(f) {
            var g = f.radioType
              , h = f.scanData;
            f = {
                id: f.id,
                customData: f.customData
            };
            g && h && Object.assign(f, {
                radioType: g,
                scanData: h
            });
            b.push(f)
        });
        return b
    }
    var Ec = function(a, b, c, d) {
        c = void 0 === c ? [] : c;
        d = void 0 === d ? [] : d;
        var e = {};
        c.forEach(function(h) {
            if ("undefined" !== typeof a.jsonPayload[h] && null !== a.jsonPayload[h])
                switch (h) {
                case "bleScanData":
                    e.bleData = a.jsonPayload[h];
                    break;
                case "customData":
                    e[h] = Ac(a.jsonPayload[h]);
                    break;
                case "deviceId":
                    e.id = a.jsonPayload[h];
                    break;
                case "mdnsScanData":
                    h = Cc(a.jsonPayload[h]);
                    e.mdnsScanData = h;
                    break;
                case "proxyDevice":
                    Object.assign(e, a.jsonPayload[h]);
                    e.proxyData = Ac(a.jsonPayload[h].proxyData);
                    e.customData = Ac(a.jsonPayload[h].customData);
                    break;
                case "udpScanData":
                    e.udpScanData = {
                        data: a.jsonPayload[h].data || a.jsonPayload[h]
                    };
                    break;
                default:
                    e[h] = a.jsonPayload[h]
                }
        });
        b = {
            requestId: a.requestId,
            inputs: [{
                intent: b,
                payload: {
                    device: e
                }
            }],
            devices: []
        };
        var f = {};
        d.forEach(function(h) {
            f[h] = a.jsonPayload[h]
        });
        d.length && (b.inputs[0].payload.params = f);
        if (d = a.structureData || a.jsonPayload.structureData)
            b.inputs[0].payload.structureData = Ac(d);
        b.devices = Dc(a);
        var g = b.inputs[0].payload.device;
        if (d = b.devices.find(function(h) {
            return h.id === g.id && !g.customData
        }))
            g.customData = d.customData;
        return b
    }
      , N = function(a, b, c, d) {
        c = void 0 === c ? [] : c;
        d = void 0 === d ? [] : d;
        c.push("id", "deviceId", "customData", "radioTypes");
        var e = c.push
          , f = e.apply;
        if (zc instanceof Array)
            var g = zc;
        else {
            g = r(zc);
            for (var h, k = []; !(h = g.next()).done; )
                k.push(h.value);
            g = k
        }
        f.call(e, c, g);
        return Ec(a, b, c, d)
    }
      , Fc = function() {
        K.call(this, "action.devices.IDENTIFY")
    };
    u(Fc, K);
    Fc.errorTransform = function(a, b) {
        if (b instanceof Gc || b instanceof Hc)
            return {
                ignoreIdentify: !0
            };
        throw b;
    }
    ;
    Fc.responseTransform = function(a, b, c) {
        c = void 0 === c ? "" : c;
        b = b.payload.device;
        var d = Bc(a.devices || [], b);
        if (!d)
            throw new O(a.requestId,"DEVICE_VERIFICATION_FAILED","VerificationId failed to match any unverified devices.");
        var e = {
            manufacturer: "UNKNOWN_MANUFACTURER",
            model: "UNKNOWN_MODEL",
            hwVersion: "UNKNOWN_HW_VERSION",
            swVersion: "UNKNOWN_SW_VERSION"
        };
        e = b.deviceInfo || e;
        d = {
            id: d,
            type: b.type || "action.devices.types.UNKNOWN",
            manufacturer: e.manufacturer || "UNKNOWN_MANUFACTURER",
            model: e.model || "UNKNOWN_MODEL",
            hwVersion: e.hwVersion || "UNKNOWN_HW_VERSION",
            swVersion: e.swVersion || "UNKNOWN_SW_VERSION",
            indicationMode: b.indicationMode || "UNDEFINED",
            isProxy: b.isProxy ? !0 : !1,
            isLocalOnly: b.isLocalOnly ? !0 : !1,
            commandedOverProxy: b.commandedOverProxy ? !0 : !1,
            requiresBonding: b.requiresBonding ? !0 : !1,
            avoidAutoconnect: b.avoidAutoconnect ? !0 : !1
        };
        b.canBeUnprovisionedOverProxy && (d.canBeUnprovisionedOverProxy = !0);
        b.canBeUpdatedOverProxy && (d.canBeUpdatedOverProxy = !0);
        b.scanMode && (d.scanMode = b.scanMode);
        b.willReportStateViaPoll && (d.willReportStateViaPoll = !0);
        if ("1.46" === c || "1.47" === c)
            c = a.devices && a.devices.length,
            a.jsonPayload.mdnsScanData && !b.isLocalOnly && c && (d.id = "fakehubfor-" + d.id,
            d.isProxy = !0,
            d.isLocalOnly = !0,
            d.commandedOverProxy = !0);
        return d
    }
    ;
    Fc.transform = function(a) {
        return N(a, "action.devices.IDENTIFY", [])
    }
    ;
    var Ic = function() {
        K.call(this, "action.devices.INDICATE")
    };
    u(Ic, K);
    Ic.transform = function(a) {
        return N(a, "action.devices.INDICATE", [], ["start"])
    }
    ;
    var Jc = function() {
        K.call(this, "action.devices.UPDATE")
    };
    u(Jc, K);
    Jc.transform = function(a) {
        return N(a, "action.devices.UPDATE", [], ["url"])
    }
    ;
    var Kc = function() {
        K.call(this, "action.devices.PROVISION")
    };
    u(Kc, K);
    Kc.responseTransform = function(a, b) {
        a = b.payload.structureData || {};
        return {
            structureData: "string" !== typeof a ? JSON.stringify(a) : a + ""
        }
    }
    ;
    Kc.transform = function(a) {
        return N(a, "action.devices.PROVISION", ["ssid", "pinCode", "passwordPlaceholder"])
    }
    ;
    var Lc = function() {
        K.call(this, "action.devices.PARSE_NOTIFICATION")
    };
    u(Lc, K);
    Lc.transform = function(a) {
        var b = N(a, "action.devices.PARSE_NOTIFICATION", ["protocol"]);
        b.inputs[0].payload.device.notificationData = a.payload.bleData;
        return b
    }
    ;
    var Mc = function() {
        K.call(this, "action.devices.NOTIFICATION")
    };
    u(Mc, K);
    Mc.transform = function(a) {
        var b = N(a, "action.devices.NOTIFICATION", ["protocol"]);
        b.inputs[0].payload.device.notificationData = a.payload.bleData;
        return b
    }
    ;
    var Nc = function() {
        K.call(this, "action.devices.PROXY_SELECTED")
    };
    u(Nc, K);
    Nc.responseTransform = function(a, b) {
        a = b.payload.proxyData;
        "string" !== typeof a && (a = JSON.stringify(a));
        return {
            proxyData: a
        }
    }
    ;
    Nc.transform = function(a) {
        return Ec(a, "action.devices.PROXY_SELECTED", ["id", "customData"])
    }
    ;
    var Oc = function() {
        K.call(this, "action.devices.REACHABLE_DEVICES")
    };
    u(Oc, K);
    Oc.responseTransform = function(a, b) {
        var c = b.payload.devices
          , d = a.devices || [];
        a = [];
        for (var e = r(c), f = e.next(); !f.done; f = e.next()) {
            f = f.value;
            var g = Bc(d, f);
            g ? a.push({
                id: g
            }) : console.error("Failed to match device " + f + " with cloud synced devices ")
        }
        c = c.length - a.length;
        0 < c && console.log("Failed to match " + c + " devices.");
        b.payload.devices = a;
        return b.payload
    }
    ;
    Oc.transform = function(a) {
        return N(a, "action.devices.REACHABLE_DEVICES", ["proxyDevice"])
    }
    ;
    var Pc = function() {
        K.call(this, "action.devices.REGISTER")
    };
    u(Pc, K);
    Pc.responseTransform = function(a, b) {
        var c = a.payload;
        a = b.requestId;
        b = b.payload.devices.map(function(d) {
            d.localId = c.localId;
            d.routableViaGcm = !0;
            d.gcmExecutionAddress = c.gcmId;
            c.roomId ? d.inferredRoom = {
                structureIdFromHint: c.structureId,
                roomIdFromHint: c.roomId
            } : c.roomName && (d.structureIdHint = c.structureId,
            d.roomHint = c.roomName);
            return d
        });
        return {
            requestId: a,
            payload: {
                devices: b
            }
        }
    }
    ;
    Pc.transform = function(a) {
        a = N(a, "action.devices.REGISTER", ["deviceName"]);
        var b = a.inputs[0].payload.device;
        b.name = b.deviceName;
        delete b.deviceName;
        return a
    }
    ;
    var Qc = function() {
        K.call(this, "action.devices.EVENT")
    };
    u(Qc, K);
    Qc.transform = function(a) {
        return N(a, "action.devices.EVENT", ["type"])
    }
    ;
    var Rc = function(a) {
        K.call(this, "action.devices.CLOUD_INTENT");
        this.trueIntent = a
    };
    u(Rc, K);
    var Sc = function(a) {
        var b = a.payload
          , c = b.requestId
          , d = b.inputs[0];
        b = d.intent;
        d = d.payload;
        var e = Ac(a.structureData);
        a = Dc(a);
        d = Object.assign({}, d, {
            structureData: e
        });
        return {
            requestId: c,
            inputs: [{
                intent: b,
                payload: d
            }],
            devices: a
        }
    };
    Rc.transform = Sc;
    var Tc = function() {
        Rc.call(this, "action.devices.QUERY")
    };
    u(Tc, Rc);
    Tc.transform = function(a) {
        if ("action.devices.CLOUD_INTENT" === a.intent)
            return Sc.call(this, a);
        var b = N(a, "action.devices.QUERY")
          , c = Ac(a.structureData);
        a = Dc(a);
        var d = b.inputs[0];
        return {
            requestId: b.requestId,
            inputs: [{
                intent: d.intent,
                payload: {
                    devices: [d.payload.device],
                    structureData: c
                }
            }],
            devices: a
        }
    }
    ;
    var Uc = function() {
        Rc.call(this, "action.devices.EXECUTE")
    };
    u(Uc, Rc);
    var Vc = function() {
        K.call(this, "action.devices.UNPROVISION")
    };
    u(Vc, K);
    Vc.transform = function(a) {
        return N(a, "action.devices.UNPROVISION")
    }
    ;
    var O = function(a, b, c) {
        b = void 0 === b ? "GENERIC_ERROR" : b;
        c = void 0 === c ? "" : c;
        var d = Error.call(this, b);
        this.message = d.message;
        "stack"in d && (this.stack = d.stack);
        this.debugString = c;
        this.errorCode = b;
        this.payload = {};
        this.response = {
            requestId: a,
            payload: {
                errorCode: b,
                debugString: c
            }
        };
        this.name = "HandlerError"
    };
    u(O, Error);
    O.prototype.toJSON = function() {
        return this.response
    }
    ;
    p.Object.defineProperties(O.prototype, {
        response: {
            configurable: !0,
            enumerable: !0,
            set: function(a) {
                this.payload = a
            },
            get: function() {
                return this.payload
            }
        }
    });
    var Wc = {
        EVENT: Qc,
        EXECUTE: Uc,
        IDENTIFY: Fc,
        INDICATE: Ic,
        NOTIFICATION: Mc,
        PARSE_NOTIFICATION: Lc,
        PROVISION: Kc,
        PROXY_SELECTED: Nc,
        QUERY: Tc,
        REACHABLE_DEVICES: Oc,
        REGISTER: Pc,
        UNPROVISION: Vc,
        UPDATE: Jc
    }
      , Gc = function(a, b) {
        O.call(this, a, "DEVICE_NOT_SUPPORTED", b);
        this.name = "DeviceNotSupportedError"
    };
    u(Gc, O);
    var Hc = function(a, b) {
        O.call(this, a, "DEVICE_NOT_IDENTIFIED", b);
        this.name = "DeviceNotIdentifiedError"
    };
    u(Hc, O);
    var Xc = function(a, b) {
        O.call(this, a, "INVALID_REQUEST", b);
        this.name = "InvalidRequestError"
    };
    u(Xc, O);
    w("smarthome.IntentFlow.DeviceNotIdentifiedError", Hc);
    w("smarthome.IntentFlow.DeviceNotSupportedError", Gc);
    w("smarthome.IntentFlow.ErrorCode", {
        NOT_SUPPORTED: "NOT_SUPPORTED",
        INVALID_REQUEST: "INVALID_REQUEST",
        INTENT_CANCELLED: "INTENT_CANCELLED",
        GENERIC_ERROR: "GENERIC_ERROR",
        DEVICE_NOT_IDENTIFIED: "DEVICE_NOT_IDENTIFIED",
        DEVICE_NOT_SUPPORTED: "DEVICE_NOT_SUPPORTED",
        DEVICE_VERIFICATION_FAILED: "DEVICE_VERIFICATION_FAILED"
    });
    w("smarthome.IntentFlow.ExecuteErrorCode", {
        ABOVE_MAXIMUM_LIGHT_EFFECTS_DURATION: "aboveMaximumLightEffectsDuration",
        ABOVE_MAXIMUM_TIMER_DURATION: "aboveMaximumTimerDuration",
        ACTION_NOT_AVAILABLE: "actionNotAvailable",
        ACTION_UNAVAILABLE_WHILE_RUNNING: "actionUnavailableWhileRunning",
        ALREADY_ARMED: "alreadyArmed",
        ALREADY_AT_MAX: "alreadyAtMax",
        ALREADY_AT_MIN: "alreadyAtMin",
        ALREADY_CLOSED: "alreadyClosed",
        ALREADY_DISARMED: "alreadyDisarmed",
        ALREADY_DOCKED: "alreadyDocked",
        ALREADY_IN_STATE: "alreadyInState",
        ALREADY_LOCKED: "alreadyLocked",
        ALREADY_OFF: "alreadyOff",
        ALREADY_ON: "alreadyOn",
        ALREADY_OPEN: "alreadyOpen",
        ALREADY_PAUSED: "alreadyPaused",
        ALREADY_STARTED: "alreadyStarted",
        ALREADY_STOPPED: "alreadyStopped",
        ALREADY_UNLOCKED: "alreadyUnlocked",
        AMBIGUOUS_ZONE_NAME: "ambiguousZoneName",
        AMOUNT_ABOVE_LIMIT: "amountAboveLimit",
        APP_LAUNCH_FAILED: "appLaunchFailed",
        ARM_FAILURE: "armFailure",
        ARM_LEVEL_NEEDED: "armLevelNeeded",
        AUTH_FAILURE: "authFailure",
        BAG_FULL: "bagFull",
        BELOW_MINIMUM_LIGHT_EFFECTS_DURATION: "belowMinimumLightEffectsDuration",
        BELOW_MINIMUM_TIMER_DURATION: "belowMinimumTimerDuration",
        BIN_FULL: "binFull",
        CANCEL_ARMING_RESTRICTED: "cancelArmingRestricted",
        CANCEL_TOO_LATE: "cancelTooLate",
        CHANNEL_SWITCH_FAILED: "channelSwitchFailed",
        CHARGER_ISSUE: "chargerIssue",
        COMMAND_INSERT_FAILED: "commandInsertFailed",
        DEAD_BATTERY: "deadBattery",
        DEGREES_OUT_OF_RANGE: "degreesOutOfRange",
        DEVICE_ALERT_NEEDS_ASSISTANCE: "deviceAlertNeedsAssistance",
        DEVICE_AT_EXTREME_TEMPERATURE: "deviceAtExtremeTemperature",
        DEVICE_BUSY: "deviceBusy",
        DEVICE_CHARGING: "deviceCharging",
        DEVICE_CLOGGED: "deviceClogged",
        DEVICE_CURRENTLY_DISPENSING: "deviceCurrentlyDispensing",
        DEVICE_DOOR_OPEN: "deviceDoorOpen",
        DEVICE_HANDLE_CLOSED: "deviceHandleClosed",
        DEVICE_JAMMING_DETECTED: "deviceJammingDetected",
        DEVICE_LID_OPEN: "deviceLidOpen",
        DEVICE_NEEDS_REPAIR: "deviceNeedsRepair",
        DEVICE_NOT_DOCKED: "deviceNotDocked",
        DEVICE_NOT_FOUND: "deviceNotFound",
        DEVICE_NOT_MOUNTED: "deviceNotMounted",
        DEVICE_NOT_READY: "deviceNotReady",
        DEVICE_STUCK: "deviceStuck",
        DEVICE_TAMPERED: "deviceTampered",
        DEVICE_THERMAL_SHUTDOWN: "deviceThermalShutdown",
        DEVICE_TURNED_OFF: "deviceTurnedOff",
        DIRECT_RESPONSE_ONLY_UNREACHABLE: "directResponseOnlyUnreachable",
        DISARM_FAILURE: "disarmFailure",
        DISCRETE_ONLY_OPEN_CLOSE: "discreteOnlyOpenClose",
        DISPENSE_AMOUNT_ABOVE_LIMIT: "dispenseAmountAboveLimit",
        DISPENSE_AMOUNT_BELOW_LIMIT: "dispenseAmountBelowLimit",
        DISPENSE_AMOUNT_REMAINING_EXCEEDED: "dispenseAmountRemainingExceeded",
        DISPENSE_FRACTIONAL_AMOUNT_NOT_SUPPORTED: "dispenseFractionalAmountNotSupported",
        DISPENSE_FRACTIONAL_UNIT_NOT_SUPPORTED: "dispenseFractionalUnitNotSupported",
        DISPENSE_UNIT_NOT_SUPPORTED: "dispenseUnitNotSupported",
        DOOR_CLOSED_TOO_LONG: "doorClosedTooLong",
        EMERGENCY_HEAT_ON: "emergencyHeatOn",
        FAULTY_BATTERY: "faultyBattery",
        FLOOR_UNREACHABLE: "floorUnreachable",
        FUNCTION_NOT_SUPPORTED: "functionNotSupported",
        GENERIC_DISPENSE_NOT_SUPPORTED: "genericDispenseNotSupported",
        HARD_ERROR: "hardError",
        IN_AUTO_MODE: "inAutoMode",
        IN_AWAY_MODE: "inAwayMode",
        IN_DRY_MODE: "inDryMode",
        IN_ECO_MODE: "inEcoMode",
        IN_FAN_ONLY_MODE: "inFanOnlyMode",
        IN_HEAT_OR_COOL: "inHeatOrCool",
        IN_HUMIDIFIER_MODE: "inHumidifierMode",
        IN_OFF_MODE: "inOffMode",
        IN_PURIFIER_MODE: "inPurifierMode",
        IN_SLEEP_MODE: "inSleepMode",
        IN_SOFTWARE_UPDATE: "inSoftwareUpdate",
        LOCK_FAILURE: "lockFailure",
        LOCKED_STATE: "lockedState",
        LOCKED_TO_RANGE: "lockedToRange",
        LOW_BATTERY: "lowBattery",
        MAX_SETTING_REACHED: "maxSettingReached",
        MAX_SPEED_REACHED: "maxSpeedReached",
        MIN_SETTING_REACHED: "minSettingReached",
        MIN_SPEED_REACHED: "minSpeedReached",
        MONITORING_SERVICE_CONNECTION_LOST: "monitoringServiceConnectionLost",
        NEEDS_ATTACHMENT: "needsAttachment",
        NEEDS_BIN: "needsBin",
        NEEDS_PADS: "needsPads",
        NEEDS_SOFTWARE_UPDATE: "needsSoftwareUpdate",
        NEEDS_WATER: "needsWater",
        NETWORK_PROFILE_NOT_RECOGNIZED: "networkProfileNotRecognized",
        NETWORK_SPEED_TEST_IN_PROGRESS: "networkSpeedTestInProgress",
        NO_AVAILABLE_APP: "noAvailableApp",
        NO_AVAILABLE_CHANNEL: "noAvailableChannel",
        NO_CHANNEL_SUBSCRIPTION: "noChannelSubscription",
        NO_TIMER_EXISTS: "noTimerExists",
        NOT_SUPPORTED: "notSupported",
        OBSTRUCTION_DETECTED: "obstructionDetected",
        OFFLINE: "offline",
        DEVICE_OFFLINE: "deviceOffline",
        ON_REQUIRES_MODE: "onRequiresMode",
        PASSPHRASE_INCORRECT: "passphraseIncorrect",
        PERCENT_OUT_OF_RANGE: "percentOutOfRange",
        PIN_INCORRECT: "pinIncorrect",
        RAIN_DETECTED: "rainDetected",
        RANGE_TOO_CLOSE: "rangeTooClose",
        RELINK_REQUIRED: "relinkRequired",
        REMOTE_SET_DISABLED: "remoteSetDisabled",
        ROOMS_ON_DIFFERENT_FLOORS: "roomsOnDifferentFloors",
        SAFETY_SHUT_OFF: "safetyShutOff",
        SCENE_CANNOT_BE_APPLIED: "sceneCannotBeApplied",
        SECURITY_RESTRICTION: "securityRestriction",
        SOFTWARE_UPDATE_NOT_AVAILABLE: "softwareUpdateNotAvailable",
        START_REQUIRES_TIME: "startRequiresTime",
        STILL_COOLING_DOWN: "stillCoolingDown",
        STILL_WARMING_UP: "stillWarmingUp",
        STREAM_UNAVAILABLE: "streamUnavailable",
        STREAM_UNPLAYABLE: "streamUnplayable",
        TANK_EMPTY: "tankEmpty",
        TARGET_ALREADY_REACHED: "targetAlreadyReached",
        TIMER_VALUE_OUT_OF_RANGE: "timerValueOutOfRange",
        TOO_MANY_FAILED_ATTEMPTS: "tooManyFailedAttempts",
        TRANSIENT_ERROR: "transientError",
        TURNED_OFF: "turnedOff",
        UNABLE_TO_LOCATE_DEVICE: "unableToLocateDevice",
        UNKNOWN_FOOD_PRESET: "unknownFoodPreset",
        UNLOCK_FAILURE: "unlockFailure",
        UNPAUSABLE_STATE: "unpausableState",
        USER_CANCELLED: "userCancelled",
        VALUE_OUT_OF_RANGE: "valueOutOfRange"
    });
    w("smarthome.IntentFlow.HandlerError", O);
    w("smarthome.IntentFlow.IndicationMode", {
        UNDEFINED: "UNDEFINED",
        BLINK: "BLINK"
    });
    w("smarthome.IntentFlow.InvalidRequestError", Xc);
    function Yc(a) {
        return v(function(b) {
            return b.return(new Promise(function(c) {
                return void setTimeout(c, a)
            }
            ))
        })
    }
    function Zc(a, b) {
        b = void 0 === b ? {} : b;
        var c = b.retryCount, d = void 0 === b.logPrefix ? "" : b.logPrefix, e = b.delayInMilliseconds, f, g, h, k;
        return v(function(l) {
            switch (l.nextAddress) {
            case 1:
                g = 0;
            case 2:
                if (!(g < c)) {
                    l.nextAddress = 4;
                    break
                }
                l.catchAddress_ = 5;
                return pa(l, a(), 7);
            case 7:
                return h = l.yieldResult,
                I(bd, d + " succeeded."),
                l.return(h);
            case 5:
                l.catchAddress_ = 0;
                var n = l.abruptCompletion_.exception;
                l.abruptCompletion_ = null;
                f = k = n;
                F(bd, d + " attempt " + g + " failed. Error: " + k + " " + k.stack);
                if (!e) {
                    l.nextAddress = 3;
                    break
                }
                return pa(l, Yc(e), 3);
            case 3:
                g++;
                l.nextAddress = 2;
                break;
            case 4:
                throw F(bd, d + " failed."),
                f;
            }
        })
    }
    var bd = E("smarthome.utilities", D);
    var cd = function() {
        return !0
    }
      , dd = function(a) {
        return a
    }
      , P = function() {
        this.eventTarget_ = new C;
        this.packets_ = {};
        this.listeners_ = []
    };
    P.prototype.toJSON = function() {
        return {
            packets: this.packets_,
            listeners: this.listeners_
        }
    }
    ;
    var ed = function(a, b) {
        return a.listeners_.find(function(c) {
            return c.id === b
        }) ? !0 : !1
    };
    P.prototype.push = function(a, b) {
        this.dispatchEvent_(a, b);
        ed(this, a) && (this.packets_[a] || (this.packets_[a] = []),
        this.packets_[a].push(b),
        fd(this, a))
    }
    ;
    P.prototype.dispatchEvent_ = function(a, b) {
        a = new gd(a,b);
        a.target = this;
        this.eventTarget_.dispatchEvent(a)
    }
    ;
    P.prototype.addEventListener = function(a, b) {
        this.eventTarget_.listen(a, b)
    }
    ;
    P.prototype.removeEventListener = function(a, b) {
        this.eventTarget_.eventTargetListeners_.remove(String(a), b, void 0, void 0)
    }
    ;
    var fd = function(a, b) {
        var c = {};
        a.listeners_.filter(function(d) {
            return d.options.n && d.id === b
        }).filter(function(d) {
            var e = d.options
              , f = e.n
              , g = e.filterFunc;
            e = a.packets_[b].filter(function(h) {
                return g(h)
            }) || [];
            if (f)
                return (f = e.length >= f) && (c[d.listenerId] = e),
                f
        }).map(function(d) {
            d.notifier.resolve(hd(c[d.listenerId], cd, d.options.transformFunc))
        });
        id(a, b)
    }
      , id = function(a, b, c) {
        c && (a.listeners_ = a.listeners_.filter(function(d) {
            return d.listenerId !== c
        }));
        ed(a, b) || delete a.packets_[b]
    };
    P.prototype.getOne = function(a, b) {
        b = void 0 === b ? {} : b;
        return this.getAll(a, {
            n: 1,
            filterFunc: void 0 === b.filterFunc ? cd : b.filterFunc,
            transformFunc: void 0 === b.transformFunc ? dd : b.transformFunc,
            timeout: b.timeout
        }).then(function(c) {
            c = void 0 === c ? [] : c;
            return c[0]
        })
    }
    ;
    P.prototype.getAll = function(a, b) {
        var c = this;
        b = void 0 === b ? {} : b;
        var d = b.n
          , e = b.timeout
          , f = void 0 === b.filterFunc ? cd : b.filterFunc
          , g = void 0 === b.transformFunc ? dd : b.transformFunc;
        return d || e ? new Promise(function(h, k) {
            var l = !1
              , n = String(Math.floor(1E5 * Math.random()))
              , y = function(A) {
                return function(G) {
                    l || (l = !0,
                    id(c, a, A),
                    G && G.length ? (I(jd, "Returning " + G.length + " packets"),
                    h(G)) : (l || F(jd, "No packets found in " + e + "ms"),
                    k(Error("No packets found in " + e + "ms"))))
                }
            }(n);
            c.listeners_.push({
                id: a,
                listenerId: n,
                options: {
                    n: d,
                    timeout: e,
                    filterFunc: f,
                    transformFunc: g
                },
                notifier: {
                    resolve: y,
                    reject: k
                }
            });
            Yc(e || 1E3).then(function() {
                return y(hd(c.packets_[a] || [], f, g))
            }).catch(function(A) {
                F(jd, "Timeout promise failed with error " + A)
            })
        }
        ) : Promise.reject(Error("Incorrect Arguments. Either n or timeout is required"))
    }
    ;
    var hd = function(a, b, c) {
        var d = [];
        b && (d = a.filter(b));
        return d.map(function(e) {
            return c(e)
        })
    };
    P.prototype.getAll = P.prototype.getAll;
    P.prototype.getOne = P.prototype.getOne;
    P.prototype.push = P.prototype.push;
    P.prototype.toJSON = P.prototype.toJSON;
    var gd = function(a, b) {
        B.call(this, a);
        this.data = b
    };
    u(gd, B);
    var jd = E("smarthome.NotificationsEmitter", D);
    var kd = {}
      , qa = (kd.SSID = {
        initiator: "CONNECT",
        follower: "DISCONNECT"
    },
    kd)
      , Q = function(a, b, c) {
        this.deviceManager_ = a;
        this.messageBus_ = c;
        this.notificationsBus_ = b;
        this.pendingCommands_ = new Map;
        this.requestIdToCommandsMap_ = new Map;
        this.queuedCommands_ = [];
        this.serializedCommandInProgress_ = !1;
        this.postHandlerHooks_ = new Map
    }
      , ld = function(a, b) {
        I(R, (void 0 === b ? "" : b) + "\n      Pending Actions: " + a.requestIdToCommandsMap_.size + "\n      Queued Commands: " + a.queuedCommands_.length + "\n      Pending Commands: " + a.pendingCommands_.size)
    };
    Q.prototype.remove = function(a) {
        ld(this, "Before processing ACTION_SUCCESS or ACTION_FAILURE");
        md(this, a);
        nd(this, a);
        od(this, a);
        ld(this, "After processing ACTION_SUCCESS or ACTION_FAILURE")
    }
    ;
    Q.prototype.cancel = function(a) {
        ld(this, "Before processing CANCEL");
        md(this, a);
        nd(this, a);
        od(this, a);
        ld(this, "After processing CANCEL")
    }
    ;
    Q.prototype.complete = function(a, b) {
        var c = this;
        if (a) {
            var d = a + ":" + b.commandId
              , e = this.pendingCommands_.get(d);
            e ? (this.pendingCommands_.delete(d),
            "platform.library.COMMAND_FAILURE" === b.type ? e.reject(new O(a,b.errorCode,b.debugString || "")) : e.resolve(b),
            pd(b) && setTimeout(function() {
                c.serializedCommandInProgress_ = !1;
                var f = c.queuedCommands_.shift();
                f && (I(R, "Sending the queued command: " + f.commandId),
                qd(c, f))
            })) : H(R, "No pending command for " + d)
        } else
            H(R, "Missing requestId: " + a)
    }
    ;
    var md = function(a, b) {
        if (b) {
            var c = a.requestIdToCommandsMap_.get(b) || [];
            c && c.length && H(R, "Final command processing for requestId: " + b);
            c.map(function(d) {
                d = b + ":" + d.commandId;
                var e = a.pendingCommands_.get(d);
                e && H(R, "Rejecting pending command: " + d);
                a.pendingCommands_.delete(d);
                return e
            }).forEach(function(d) {
                d && d.reject(Error("INTENT_CANCELLED"))
            });
            a.requestIdToCommandsMap_.delete(b)
        } else
            H(R, "Missing requestId: " + b)
    }
      , td = function(a, b, c, d, e) {
        var f = b.requestId
          , g = b.commandId;
        a.pendingCommands_.set(f + ":" + g, new rd(function(k) {
            var l = b.requestId
              , n = b.protocol;
            if (qa[n]) {
                var y = qa[n].initiator
                  , A = b.operation;
                l = l + ":" + n;
                n = a.postHandlerHooks_.has(l);
                y !== A || n || (I(R, "Scheduling post hook for " + JSON.stringify(l)),
                a.postHandlerHooks_.set(l, sd(a, b)))
            }
            b instanceof tc && Object.assign(k, {
                characteristicUuid: b.characteristicUuid,
                serviceUuid: b.serviceUuid
            });
            c ? (I(R, "COMMAND_SUCCESS for command: " + g),
            d(k)) : I(R, "Waiting for Notification for: " + g);
            ld(a, "After processing COMMAND -> COMMAND_SUCCESS")
        }
        ,function(k) {
            e(k);
            ld(a, "After processing COMMAND -> COMMAND_FAILURE")
        }
        ));
        var h = a.requestIdToCommandsMap_.get(f) || [];
        h.push(b);
        a.requestIdToCommandsMap_.set(f, h)
    }
      , pd = function(a) {
        return a instanceof rc || "TCP" === a.protocol
    }
      , nd = function(a, b) {
        a.queuedCommands_ = a.queuedCommands_.filter(function(c) {
            return c.requestId !== b
        })
    }
      , qd = function(a, b) {
        var c = b.commandId;
        a.serializedCommandInProgress_ && pd(b) ? (H(R, "Queuing the command: " + c),
        a.queuedCommands_.push(b)) : (pd(b) && (a.serializedCommandInProgress_ = !0),
        I(R, "Sending the command: " + c),
        a.messageBus_.send(b),
        ld(a, "After sending COMMAND"))
    };
    Q.prototype.getQueuedCommands = function() {
        return this.queuedCommands_
    }
    ;
    Q.prototype.sendAndWait = function(a, b, c) {
        b = void 0 === b ? {} : b;
        var d = b.n, e = b.filterFunc, f = b.transformFunc, g = b.timeout, h = (void 0 === c ? {} : c).commandTimeout, k = this, l, n, y, A, G, fa;
        return v(function(ta) {
            a.commandId_ = mc++;
            ld(k, "Before sending COMMAND");
            l = a;
            n = l.commandId;
            y = l.deviceId;
            A = l.requestId;
            G = l.protocol;
            (fa = d || g ? !0 : !1) && !g && (g = 5E3);
            return ta.return(new Promise(function(Ub, $c) {
                if (fa) {
                    var ad = k.deviceManager_.getProxyInfo(y);
                    k.notificationsBus_.getAll(ad ? ad.proxyDeviceId : y, {
                        n: d,
                        filterFunc: e,
                        transformFunc: f,
                        timeout: g
                    }).then(function(Ba) {
                        return d && 1 === d ? Ub(Ba[0]) : Ub(Ba)
                    }).catch($c)
                } else
                    h && 1E3 <= h && setTimeout(function() {
                        var Ba = new yc(G);
                        Object.assign(Ba, {
                            requestId: A,
                            commandId: n,
                            deviceId: y,
                            errorCode: "COMMAND_TIMEOUT",
                            debugString: "Command timed out"
                        });
                        k.complete(A, Ba);
                        I(R, "Completed timeout function for cmd " + n)
                    }, h);
                td(k, a, !fa, Ub, $c);
                qd(k, a)
            }
            ))
        })
    }
    ;
    Q.prototype.send = function(a, b) {
        var c = this
          , d = void 0 === b ? {} : b
          , e = d.commandTimeout;
        b = void 0 === d.retries ? 0 : d.retries;
        d = void 0 === d.delayInMilliseconds ? 0 : d.delayInMilliseconds;
        return a.waitForNotification ? this.sendAndWait(a, {
            n: 1
        }) : b ? Zc(function() {
            return v(function(f) {
                return 1 == f.nextAddress ? pa(f, c.sendAndWait(a, void 0, {
                    commandTimeout: e
                }), 2) : f.return(f.yieldResult)
            })
        }, {
            delayInMilliseconds: d,
            logPrefix: a.protocol,
            retryCount: Math.min(b, 3)
        }) : this.sendAndWait(a, void 0, {
            commandTimeout: e
        })
    }
    ;
    var ud = function(a, b) {
        if ("BLE" === b.payload.protocol) {
            var c = new xc;
            c.requestId = b.requestId;
            c.deviceId = b.payload.deviceId;
            var d = b.payload.bleData;
            c.bleResponse = {
                characteristicUuid: d.characteristicUuid,
                serviceUuid: d.serviceUuid,
                value: d.value
            };
            I(R, "Pushing to NotificationsBus " + JSON.stringify(c));
            a.notificationsBus_.push(b.payload.deviceId, c)
        }
    }
      , sd = function(a, b) {
        var c = b.requestId
          , d = b.deviceId;
        return function(e) {
            var f;
            return v(function(g) {
                if (e)
                    return I(R, "Running SSID DISCONNECT hook for " + c),
                    f = new vc,
                    Object.assign(f, {
                        requestId: c,
                        deviceId: d,
                        operation: "DISCONNECT"
                    }),
                    pa(g, a.send(f, {
                        retries: 3
                    }), 0);
                g.nextAddress = 0
            })
        }
    };
    Q.prototype.runPostHandlerHooks = function(a, b) {
        var c = this, d, e, f, g, h;
        return v(function(k) {
            1 == k.nextAddress && (e = new ra);
            a: {
                for (; 0 < e.properties_.length; ) {
                    var l = e.properties_.pop();
                    if (l in e.object_)
                        break a
                }
                l = null
            }
            if (null == (d = l))
                k.nextAddress = 0;
            else {
                f = a + ":" + d;
                I(R, "Looking for hooks for " + f);
                if (g = c.postHandlerHooks_.has(f))
                    return h = c.postHandlerHooks_.get(f),
                    pa(k, h(b), 2);
                k.nextAddress = 2
            }
        })
    }
    ;
    var od = function(a, b) {
        for (var c in qa) {
            var d = b + ":" + c;
            a.postHandlerHooks_.has(d) && (I(R, "Removing the hooks for " + d),
            a.postHandlerHooks_.delete(d))
        }
    };
    Q.prototype.runPostHandlerHooks = Q.prototype.runPostHandlerHooks;
    Q.prototype.send = Q.prototype.send;
    Q.prototype.sendAndWait = Q.prototype.sendAndWait;
    Q.prototype.getQueuedCommands = Q.prototype.getQueuedCommands;
    Q.prototype.complete = Q.prototype.complete;
    Q.prototype.cancel = Q.prototype.cancel;
    var rd = function(a, b) {
        this.resolve = a;
        this.reject = b
    }
      , R = E("smarthome.CommandManager", D);
    var yd = function(a) {
        this.deviceManager_ = a;
        vd(this);
        wd(this);
        xd(this)
    }
      , vd = function(a) {
        a.deviceManager_.setIntentHandler("action.devices.PROXY_SELECTED", function(b) {
            return {
                requestId: b.requestId,
                intent: b.inputs[0].intent,
                payload: {
                    proxyData: {}
                }
            }
        })
    }
      , wd = function(a) {
        a.deviceManager_.setIntentHandler("action.devices.REACHABLE_DEVICES", function(b) {
            var c = b.inputs[0].intent
              , d = b.inputs[0].payload.device.id
              , e = RegExp("fakehubfor-");
            if (!e.test(d))
                throw new O(b.requestId,"INVALID_REQUEST","Real device corresponding to simulated hub is not found.");
            e = d.replace(e, "");
            return {
                requestId: b.requestId,
                intent: c,
                payload: {
                    devices: [{
                        id: e
                    }, {
                        id: d
                    }]
                }
            }
        })
    }
      , xd = function(a) {
        a.deviceManager_.setIntentHandler("action.devices.UNPROVISION", function(b) {
            return {
                requestId: b.requestId,
                intent: b.inputs[0].intent,
                payload: {}
            }
        })
    };
    var zd = new Map;
    var S = function(a) {
        if (!a || "urn:x-cast:com.google.cast.generic" != a.namespace_)
            throw Error("Invalid message bus");
        this.messageBus_ = a;
        this.messageBus_.onMessage = this.onMessage_.bind(this);
        this.handlers_ = new Map;
        this.cancelledActions_ = new Set;
        this.eventListeners_ = new Map;
        Ad(this);
        new yd(this);
        this.requestIdToStateMap_ = new Map;
        this.registeredDevices_ = [];
        this.notificationsBus_ = new P;
        this.commandManager_ = new Q(this,this.notificationsBus_,this.messageBus_);
        this.cloudLogger_ = new ic(this,this.messageBus_)
    }
      , kc = function(a) {
        var b = a.intent;
        if ("action.devices.CLOUD_INTENT" === b)
            try {
                b = a.payload.inputs[0].intent
            } catch (c) {
                F(T, "Failed to get real intent, using CLOUD_INTENT"),
                b = "action.devices.CLOUD_INTENT"
            }
        else
            "action.devices.LOCAL_INTENT" === b && (b = a.payload.trueIntent);
        return b.replace("action.devices.", "")
    };
    S.prototype.setMessageHandler = function(a, b) {
        if (null !== b && "function" !== typeof b)
            throw F(T, "Given handler is not a function or null"),
            Error("Given handler is not a function or null");
        if ((a = a.replace("action.devices.", "")) && gc[a])
            null === b ? this.handlers_.delete(a) : this.handlers_.set(a, b);
        else
            throw b = "Cannot set handler for " + a,
            F(T, b),
            Error(b);
    }
    ;
    S.prototype.setIntentHandler = function(a, b) {
        this.setMessageHandler(a, b)
    }
    ;
    var U = function(a, b) {
        var c = "";
        b && (c += "" + b);
        c += "  Cancelled Actions: " + a.cancelledActions_.size + "\n";
        I(T, c)
    }
      , Bd = function(a) {
        if ("action.devices.CLOUD_INTENT" === a.intent) {
            var b = a.payload.inputs[0].intent;
            if ("action.devices.EXECUTE" === b)
                return a.payload.inputs[0].payload.commands[0].devices.map(function(c) {
                    return c.id
                });
            if ("action.devices.QUERY" === b)
                return a.payload.inputs[0].payload.devices.map(function(c) {
                    return c.id
                })
        }
        return a.payload.id ? [a.payload.id] : []
    }
      , Ed = function(a, b) {
        U(a, "Before processing ACTION_START");
        b = b.data;
        var c = b.intent;
        b.receivedAt = Date.now();
        c = b.payload;
        if ("string" === typeof c)
            try {
                c = JSON.parse(b.payload),
                b.jsonPayload = c
            } catch (e) {
                Cd(a, "Incorrect Payload for message", b, "INVALID_REQUEST");
                return
            }
        b.payload = c;
        if ((c = kc(b)) && gc[c] && Wc[c]) {
            b.requestJSON = Wc[c].transform(b);
            var d = b.requestJSON.devices || [];
            d.length && (a.registeredDevices_ = d);
            Bd(b).forEach(function(e) {
                zd.delete(e)
            });
            d = b.proxyInfo;
            Array.isArray(d) && d.forEach(function(e) {
                zd.set(e.targetDeviceId, e)
            });
            "action.devices.NOTIFICATION" === b.intent && (ud(a.commandManager_, b),
            d = Wc.PARSE_NOTIFICATION.transform(b),
            c = "PARSE_NOTIFICATION",
            b.intent = "action.devices.PARSE_NOTIFICATION",
            b.requestJSON = d);
            (d = a.handlers_.get(c)) ? Dd(a, b, d) : Cd(a, "Handler for " + c + " not implemented", b, "NOT_SUPPORTED")
        } else
            Cd(a, "Unsupported intent:" + c, b, "NOT_SUPPORTED")
    };
    S.prototype.onMessage_ = function(a) {
        var b = a.data
          , c = b.type;
        switch (c) {
        case "platform.library.APPLICATION_READY_RESPONSE":
            H(T, "Cast shell version: " + b.castBuildRelease);
            H(T, "SDK version: 1.5.4");
            this.castBuildRelease_ = b.castBuildRelease;
            break;
        case "platform.library.ACTION_START":
            Ed(this, a);
            break;
        case "platform.library.ACTION_CANCEL":
            (a = b.requestId) && "platform.library.ACTION_CANCEL" == b.type && (U(this, "Before processing ACTION_CANCEL"),
            this.cancelledActions_.add(a),
            this.commandManager_.cancel(a),
            U(this, "After processing ACTION_CANCEL"));
            break;
        case "platform.library.COMMAND_SUCCESS":
            this.commandManager_.complete(b.requestId, b);
            break;
        case "platform.library.COMMAND_FAILURE":
            this.commandManager_.complete(b.requestId, b);
            break;
        case "platform.library.LOG":
            switch (b.logLevel) {
            case "WARNING":
                H(T, "Platform says: " + b.message);
                break;
            case "ERROR":
                F(T, "Platform says: " + b.message);
                break;
            default:
                I(T, "Platform says: " + b.message)
            }
            break;
        default:
            Fd(this, "Unsupported event " + c, b, "INVALID_REQUEST")
        }
    }
    ;
    var Dd = function(a, b, c) {
        Promise.resolve().then(function() {
            return c(b.requestJSON)
        }).then(function(d) {
            var e = b.requestId;
            a.cancelledActions_.has(e) ? (a.cancelledActions_.delete(e),
            a.requestIdToStateMap_.delete(e),
            U(a, "After processing ACTION_CANCEL"),
            e = !0) : e = !1;
            if (e)
                throw H(T, "Action already cancelled, reqId: " + b.requestId),
                new fc("ACTION_CANCELLED");
            return d
        }).then(function(d) {
            return Gd(a, b.requestId, !1).then(function() {
                return d
            }).catch(function() {
                F(T, "Swallowing post handler hook failure");
                return d
            })
        }).then(function(d) {
            if (!d)
                throw Error("Cannot handle this intentResponse");
            b: switch (b.intent) {
            case "action.devices.IDENTIFY":
            case "action.devices.PROVISION":
            case "action.devices.PROXY_SELECTED":
            case "action.devices.REACHABLE_DEVICES":
            case "action.devices.REGISTER":
                var e = !0;
                break b;
            default:
                e = !1
            }
            e ? (e = kc(b),
            d = Wc[e].responseTransform(b, d, a.castBuildRelease_)) : ["action.devices.CLOUD_INTENT", "action.devices.EXECUTE"].includes(b.intent) ? d.metrics = {
                latencyInMilliseconds: Date.now() - b.receivedAt,
                receivedAt: b.receivedAt,
                source: "local_home_sdk"
            } : d = "action.devices.PARSE_NOTIFICATION" === b.intent ? d.payload.devices || d.payload : d.payload;
            d = Hd(a, b, d);
            "action.devices.REGISTER" === b.intent ? (e = JSON.parse(d.payload || "{}"),
            d.agentDeviceId = e.payload.devices[0].id + "") : "action.devices.UNPROVISION" === b.intent && b.payload.id && zd.delete(b.payload.id);
            d = Id(b, d);
            a.commandManager_.remove(b.requestId);
            U(a, "After processing ACTION_START -> ACTION SUCCESS");
            a.messageBus_.send(d);
            a: switch (b.intent) {
            case "action.devices.PROXY_SELECTED":
            case "action.devices.REACHABLE_DEVICES":
            case "action.devices.CLOUD_INTENT":
            case "action.devices.QUERY":
            case "action.devices.EXECUTE":
                d = !1;
                break a;
            default:
                d = !0
            }
            d && Jd(a, b)
        }).catch(function(d) {
            return Gd(a, b.requestId, !0).catch(function() {
                F(T, "Swallowing post handler hook failure")
            }).then(function() {
                throw d;
            })
        }).catch(function(d) {
            F(T, "Intent handler failed with error: " + d.message);
            I(T, d.stack);
            if (d instanceof fc && "ACTION_CANCELLED" === d.errorCode)
                Jd(a, b, d),
                a.commandManager_.remove(b.requestId);
            else if (d instanceof Gc || d instanceof Hc) {
                if (!d)
                    throw Error("Cannot handle this intentResponse");
                var e = b.intent;
                d && "action.devices.IDENTIFY" === e ? (e = kc(b),
                d = Wc[e].errorTransform(b, d)) : d = b;
                d = Hd(a, b, d);
                d = Id(b, d);
                U(a, "After processing ACTION_START -> ACTION SUCCESS");
                a.messageBus_.send(d)
            } else
                d instanceof O ? (e = Kd(b, d, "APP_ERROR"),
                U(a, "After processing ACTION_START -> specific ACTION_FAILURE"),
                a.messageBus_.send(e),
                Jd(a, b, d)) : d instanceof Error ? Cd(a, "Got a rejected promise " + d.message, b, "APP_ERROR") : Cd(a, "Got a rejected promise " + JSON.stringify(d), b, "APP_ERROR"),
                a.commandManager_.remove(b.requestId)
        }).finally(function() {
            a.cloudLogger_.sendLogs(b)
        })
    }
      , Id = function(a, b) {
        if (!b)
            return Ld("No response data", a, "APP_ERROR");
        switch (b.type) {
        case "library.platform.ACTION_SUCCESS":
        case "library.platform.ACTION_PENDING":
        case "library.platform.ACTION_FAILURE":
            return b.requestId = a.requestId,
            b
        }
        return Ld("Invalid response data " + JSON.stringify(b), a, "APP_ERROR")
    }
      , Ld = function(a, b, c) {
        F(T, a);
        a = new ec(c,a);
        a.requestId = b.requestId;
        a.payload = JSON.stringify({});
        return a
    }
      , Fd = function(a, b, c, d) {
        b = Ld(b, c, d);
        U(a, "After processing a MESSAGE -> FAILURE");
        a.messageBus_.send(b)
    }
      , Kd = function(a, b, c) {
        c = c || "APP_ERROR";
        var d = b.debugString || "";
        F(T, d);
        c = new ec(c,d);
        c.requestId = a.requestId;
        c.intent = gc[kc(a)];
        c.payload = JSON.stringify(b);
        return c
    }
      , Cd = function(a, b, c, d) {
        b = new O(c.requestId,"unknownError",b);
        d = Kd(c, b, d);
        U(a, "After processing ACTION_START -> generic ACTION_FAILURE");
        a.messageBus_.send(d);
        Jd(a, c, b)
    };
    S.prototype.start = function(a) {
        var b = this;
        this.appVersion_ = a;
        var c = new $b;
        c.requestId = "" + Date.now();
        return new Promise(function(d) {
            d({});
            b.messageBus_.send(c)
        }
        )
    }
    ;
    S.prototype.sendAndWait = function(a, b, c) {
        b = void 0 === b ? {} : b;
        var d = b.n, e = b.filterFunc, f = b.transformFunc, g = b.timeout, h = (void 0 === c ? {} : c).commandTimeout, k = this, l;
        return v(function(n) {
            l = {
                n: d,
                filterFunc: e,
                transformFunc: f,
                timeout: g
            };
            return k.cancelledActions_.has(a.requestId) ? n.return(Promise.reject(Error("INTENT_CANCELLED"))) : n.return(k.commandManager_.sendAndWait(a, l, {
                commandTimeout: h
            }))
        })
    }
    ;
    S.prototype.send = function(a, b) {
        return this.cancelledActions_.has(a.requestId) ? Promise.reject(Error("INTENT_CANCELLED")) : this.commandManager_.send(a, b)
    }
    ;
    var Hd = function(a, b, c) {
        var d = new cc;
        if ("action.devices.PARSE_NOTIFICATION" === b.intent) {
            var e = a.requestIdToStateMap_.get(b.requestId);
            var f = c && c.states;
            e = e && Md(e) || f ? "action.devices.REPORT_STATE" : "action.devices.NOTIFICATION"
        } else
            e = hc[kc(b)];
        d.intent = e;
        d.requestId = b.requestId;
        d.payload = JSON.stringify(c || {});
        f = (e = a.requestIdToStateMap_.get(b.requestId)) && Md(e);
        e && a.requestIdToStateMap_.delete(b.requestId);
        f ? c = JSON.stringify(e.payload.devices) : (a = c && c.states,
        c = "action.devices.PARSE_NOTIFICATION" === b.intent && a ? JSON.stringify(c) : void 0);
        c && (d.reportStatePayload = c,
        "action.devices.PARSE_NOTIFICATION" === b.intent && (d.payload = c));
        return d
    };
    S.prototype.markPending = function(a, b) {
        var c = this
          , d = new dc;
        d.requestId = a.requestId;
        d.intent = a.inputs[0].intent;
        d.payload = JSON.stringify(b || {});
        return Promise.resolve().then(function() {
            var e = Id(d, d);
            c.messageBus_.send(e)
        }).catch(function(e) {
            I(T, e.stack);
            F(T, "Got a rejected promise " + e.message);
            Fd(c, "Got a rejected promise " + JSON.stringify(e), d, "APP_ERROR")
        })
    }
    ;
    S.prototype.getProxyInfo = function(a) {
        return zd.get(a)
    }
    ;
    S.prototype.setLoggerLevel = function(a) {
        T && (Kb(Lb(), T.getName()).level = a)
    }
    ;
    var Ad = function(a) {
        a.setIntentHandler("action.devices.EVENT", function(b) {
            return Nd(a, b)
        })
    }
      , Nd = function(a, b) {
        var c, d, e, f;
        return v(function(g) {
            return 1 == g.nextAddress ? (c = b.inputs[0].payload.device,
            d = c.type || "",
            e = a.eventListeners_.get(d.toLowerCase()),
            I(T, "Event type: " + d + ", received for device id: " + c.id),
            e ? pa(g, e(b), 2) : (f = {
                requestId: b.requestId,
                intent: b.inputs[0].intent,
                payload: {}
            },
            g.return(f))) : g.return(g.yieldResult)
        })
    };
    S.prototype.reportState = function(a) {
        a && a.requestId && this.requestIdToStateMap_.set(a.requestId, a)
    }
    ;
    S.prototype.setEventListener = function(a, b) {
        a = a || "";
        b ? this.eventListeners_.set(a.toLowerCase(), b) : H(T, "Listener could not be set for event: " + a)
    }
    ;
    var Jd = function(a, b, c) {
        var d = Date.now();
        d = {
            requestId: b.requestId,
            timestamp: {
                seconds: Math.floor(d / 1E3),
                nanos: d % 1E3 * 1E6
            },
            appVersion: a.appVersion_ || "unknownVersion",
            intent: b.intent,
            severity: c ? "ERROR" : "INFO"
        };
        c && (d.message = JSON.stringify(c),
        d.errorCode = c.errorCode);
        b = {
            requestId: b.requestId,
            type: "library.platform.LOG",
            logEntries: [d]
        };
        (c ? F : I)(T, "Logging to stackdriver: " + JSON.stringify(d));
        a.messageBus_.sendLogs(b)
    };
    S.prototype.getRegisteredDevices = function() {
        return this.registeredDevices_ || []
    }
    ;
    var Gd = function(a, b, c) {
        return v(function(d) {
            return pa(d, a.commandManager_.runPostHandlerHooks(b, c), 0)
        })
    };
    S.prototype.getRegisteredDevices = S.prototype.getRegisteredDevices;
    S.prototype.setEventListener = S.prototype.setEventListener;
    S.prototype.reportState = S.prototype.reportState;
    S.prototype.setLoggerLevel = S.prototype.setLoggerLevel;
    S.prototype.getProxyInfo = S.prototype.getProxyInfo;
    S.prototype.markPending = S.prototype.markPending;
    S.prototype.send = S.prototype.send;
    S.prototype.sendAndWait = S.prototype.sendAndWait;
    S.prototype.start = S.prototype.start;
    S.prototype.setIntentHandler = S.prototype.setIntentHandler;
    S.prototype.setMessageHandler = S.prototype.setMessageHandler;
    var T = E("smarthome.DeviceManager", D);
    function Md(a) {
        a = a.payload;
        return !!(a && a.devices && a.devices.states)
    }
    ;var Od = function() {
        this.relativeTimeStart_ = Date.now()
    }
      , Pd = null;
    Od.prototype.set = function(a) {
        this.relativeTimeStart_ = a
    }
    ;
    Od.prototype.reset = function() {
        this.set(Date.now())
    }
    ;
    Od.prototype.get = function() {
        return this.relativeTimeStart_
    }
    ;
    var Qd = function(a) {
        this.prefix_ = a || "";
        Pd || (Pd = new Od);
        this.startTimeProvider_ = Pd
    };
    m = Qd.prototype;
    m.appendNewline = !0;
    m.showAbsoluteTime = !0;
    m.showRelativeTime = !0;
    m.showLoggerName = !0;
    m.showExceptionText = !1;
    m.showSeverityLevel = !1;
    var Rd = function(a) {
        return 10 > a ? "0" + a : String(a)
    }
      , Sd = function(a) {
        Qd.call(this, a)
    };
    Ha(Sd, Qd);
    var Td = function(a, b) {
        var c = [];
        c.push(a.prefix_, " ");
        if (a.showAbsoluteTime) {
            var d = new Date(b.time_);
            c.push("[", Rd(d.getFullYear() - 2E3) + Rd(d.getMonth() + 1) + Rd(d.getDate()) + " " + Rd(d.getHours()) + ":" + Rd(d.getMinutes()) + ":" + Rd(d.getSeconds()) + "." + Rd(Math.floor(d.getMilliseconds() / 10)), "] ")
        }
        if (a.showRelativeTime) {
            d = c.push;
            var e = a.startTimeProvider_.get();
            e = (b.time_ - e) / 1E3;
            var f = e.toFixed(3)
              , g = 0;
            if (1 > e)
                g = 2;
            else
                for (; 100 > e; )
                    g++,
                    e *= 10;
            for (; 0 < g--; )
                f = " " + f;
            d.call(c, "[", f, "s] ")
        }
        a.showLoggerName && c.push("[", b.loggerName_, "] ");
        a.showSeverityLevel && c.push("[", b.level_.name, "] ");
        c.push(b.msg_);
        a.showExceptionText && (b = b.exception_,
        void 0 !== b && c.push("\n", b instanceof Error ? b.message : String(b)));
        a.appendNewline && c.push("\n");
        return c.join("")
    };
    var Ud = function() {
        this.publishHandler_ = Fa(this.addLogRecord, this);
        this.formatter_ = new Sd;
        this.formatter_.showAbsoluteTime = !1;
        this.formatter_.showExceptionText = !1;
        this.isCapturing_ = this.formatter_.appendNewline = !1;
        this.filteredLoggers_ = {}
    };
    Ud.prototype.addLogRecord = function(a) {
        function b(f) {
            if (f) {
                if (f.value >= yb.value)
                    return "error";
                if (f.value >= D.value)
                    return "warn";
                if (f.value >= Ab.value)
                    return "log"
            }
            return "debug"
        }
        if (!this.filteredLoggers_[a.loggerName_]) {
            var c = Td(this.formatter_, a)
              , d = Vd;
            if (d) {
                var e = b(a.level_);
                Wd(d, e, c, a.exception_)
            }
        }
    }
    ;
    var Xd = null
      , Vd = Aa.console
      , Wd = function(a, b, c, d) {
        if (a[b])
            a[b](c, void 0 === d ? "" : d);
        else
            a.log(c, void 0 === d ? "" : d)
    };
    var V = function() {
        z.call(this);
        Xd || (Xd = new Ud);
        if (Xd) {
            var a = Xd;
            if (1 != a.isCapturing_) {
                var b = Kb(Lb(), "").logger
                  , c = a.publishHandler_;
                b && Kb(Lb(), b.getName()).handlers.push(c);
                a.isCapturing_ = !0
            }
        }
        I(Yd, "Version: 1.5.4");
        this.ipcChannel_ = new Rb;
        this.ipcChannel_.open();
        this.messageBus_ = new Vb("urn:x-cast:com.google.cast.generic","smarthomejs",this.ipcChannel_,"JSON");
        Na(this, Ga(Ma, this.messageBus_));
        this.messageBus_.onMessage = this.onMessage_.bind(this);
        this.messageBusesByNamespace_ = {};
        this.deviceManager_ = null
    };
    u(V, z);
    V.prototype.getDeviceManager = function() {
        this.deviceManager_ || (this.deviceManager_ = new S(Zd(this, "urn:x-cast:com.google.cast.generic", "JSON")));
        return this.deviceManager_
    }
    ;
    V.prototype.getMessageBus = function(a, b) {
        if ("urn:x-cast:com.google.cast.generic" == a)
            throw Error("Protected namespace");
        return Zd(this, a, b)
    }
    ;
    var Zd = function(a, b, c) {
        if (0 != b.lastIndexOf("urn:x-cast:", 0))
            throw Error("Invalid namespace prefix");
        a.messageBusesByNamespace_[b] || (a.messageBusesByNamespace_[b] = new Vb(b,"smarthomejs",a.ipcChannel_,c),
        Na(a, Ga(Ma, a.messageBusesByNamespace_[b])));
        if (c && a.messageBusesByNamespace_[b].messageType_ != c)
            throw Error("Invalid messageType for the namespace");
        return a.messageBusesByNamespace_[b]
    };
    V.prototype.isSystemReady = function() {
        return !0
    }
    ;
    V.prototype.onMessage_ = function() {}
    ;
    var ae = function() {
        $d || ($d = new V);
        return $d
    };
    V.prototype.setLoggerLevel = function(a) {
        Yd && (Kb(Lb(), Yd.getName()).level = a)
    }
    ;
    V.prototype.setLoggerLevel = V.prototype.setLoggerLevel;
    V.getInstance = ae;
    V.prototype.isSystemReady = V.prototype.isSystemReady;
    V.prototype.getMessageBus = V.prototype.getMessageBus;
    V.prototype.getDeviceManager = V.prototype.getDeviceManager;
    var $d = null
      , Yd = E("smarthome.DeviceContext", D);
    var W = function(a, b) {
        a || H(be, "Missing app version. It is helpful in analyzing stackdriver logs.");
        this.version = a || "0.0.1";
        this.deviceManager_ = b
    };
    m = W.prototype;
    m.getDeviceManager = function() {
        this.deviceManager_ || (this.deviceManager_ = ae().getDeviceManager());
        return this.deviceManager_
    }
    ;
    m.getLogger = function() {
        return this.getDeviceManager().cloudLogger_
    }
    ;
    m.onIdentify = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.IDENTIFY", a);
        return this
    }
    ;
    m.onIndicate = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.INDICATE", a);
        return this
    }
    ;
    m.onProvision = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.PROVISION", a);
        return this
    }
    ;
    m.onRegister = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.REGISTER", a);
        return this
    }
    ;
    m.onQuery = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.QUERY", a);
        return this
    }
    ;
    m.onExecute = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.EXECUTE", a);
        return this
    }
    ;
    m.onUpdate = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.UPDATE", a);
        return this
    }
    ;
    m.onUnprovision = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.UNPROVISION", a);
        return this
    }
    ;
    m.onProxySelected = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.PROXY_SELECTED", a);
        return this
    }
    ;
    m.onReachableDevices = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.REACHABLE_DEVICES", a);
        return this
    }
    ;
    m.onParseNotification = function(a) {
        this.getDeviceManager().setIntentHandler("action.devices.PARSE_NOTIFICATION", a);
        return this
    }
    ;
    m.on = function(a, b) {
        this.getDeviceManager().setEventListener(a, b);
        return this
    }
    ;
    m.listen = function() {
        var a = this;
        return this.getDeviceManager().start(this.version).then(function() {
            return console.log("Ready, App version: " + a.version)
        })
    }
    ;
    W.prototype.listen = W.prototype.listen;
    W.prototype.on = W.prototype.on;
    W.prototype.onParseNotification = W.prototype.onParseNotification;
    W.prototype.onReachableDevices = W.prototype.onReachableDevices;
    W.prototype.onProxySelected = W.prototype.onProxySelected;
    W.prototype.onUnprovision = W.prototype.onUnprovision;
    W.prototype.onUpdate = W.prototype.onUpdate;
    W.prototype.onExecute = W.prototype.onExecute;
    W.prototype.onQuery = W.prototype.onQuery;
    W.prototype.onRegister = W.prototype.onRegister;
    W.prototype.onProvision = W.prototype.onProvision;
    W.prototype.onIndicate = W.prototype.onIndicate;
    W.prototype.onIdentify = W.prototype.onIdentify;
    var be = E("smarthome.App", D);
    w("smarthome.App", W);
    var ce = function(a) {
        this.requestId = a.requestId;
        this.successDevices = a.successDevices;
        this.errorDevices = a.errorDevices;
        this.response = {
            requestId: this.requestId,
            payload: {
                commands: []
            }
        }
    };
    ce.prototype.toJSON = function() {
        this.response = {
            requestId: this.requestId,
            payload: {
                commands: []
            }
        };
        for (var a in this.successDevices)
            this.response.payload.commands.push({
                ids: [a],
                status: "SUCCESS",
                states: this.successDevices[a]
            });
        for (var b in this.errorDevices)
            this.response.payload.commands.push({
                ids: this.errorDevices[b],
                status: "ERROR",
                errorCode: b,
                states: {}
            });
        return this.response
    }
    ;
    ce.prototype.toJSON = ce.prototype.toJSON;
    var X = function() {
        this.requestId = "";
        this.successDevices = {};
        this.errorDevices = {}
    };
    X.prototype.setRequestId = function(a) {
        this.requestId = a;
        return this
    }
    ;
    X.prototype.setSuccessState = function(a, b) {
        this.successDevices[a] = b;
        return this
    }
    ;
    X.prototype.setErrorState = function(a, b) {
        this.errorDevices[b] || (this.errorDevices[b] = []);
        this.errorDevices[b].push(a);
        return this
    }
    ;
    X.prototype.build = function() {
        return (new ce(this)).toJSON()
    }
    ;
    X.prototype.build = X.prototype.build;
    X.prototype.setErrorState = X.prototype.setErrorState;
    X.prototype.setSuccessState = X.prototype.setSuccessState;
    X.prototype.setRequestId = X.prototype.setRequestId;
    w("smarthome.Execute.Response.Builder", X);
    var de = function(a) {
        this.requestId = a.requestId;
        this.agentUserId = a.agentUserId;
        this.states = a.states;
        this.notifications = a.notifications
    };
    de.prototype.toJSON = function() {
        return this.response = {
            requestId: this.requestId,
            agentUserId: this.agentUserId,
            payload: {
                devices: {
                    states: this.states
                }
            }
        }
    }
    ;
    de.prototype.toJSON = de.prototype.toJSON;
    var Y = function() {
        this.agentUserId = this.requestId = "";
        this.states = {};
        this.notifications = {}
    };
    m = Y.prototype;
    m.setRequestId = function(a) {
        this.requestId = a;
        return this
    }
    ;
    m.setAgentUserId = function(a) {
        this.agentUserId = a;
        return this
    }
    ;
    m.setState = function(a, b) {
        this.states[a] = b;
        return this
    }
    ;
    m.setNotification = function(a, b) {
        this.notifications[a] = b;
        return this
    }
    ;
    m.build = function() {
        return (new de(this)).toJSON()
    }
    ;
    Y.prototype.build = Y.prototype.build;
    Y.prototype.setNotification = Y.prototype.setNotification;
    Y.prototype.setState = Y.prototype.setState;
    Y.prototype.setAgentUserId = Y.prototype.setAgentUserId;
    Y.prototype.setRequestId = Y.prototype.setRequestId;
    w("smarthome.ReportState.Response.Builder", Y);
    var Z = function() {
        this.cache_ = new Map
    };
    Z.prototype.setItem = function(a, b) {
        this.cache_.set(a, b)
    }
    ;
    Z.prototype.getItem = function(a) {
        return this.cache_.has(a) ? this.cache_.get(a) : null
    }
    ;
    Z.prototype.removeItem = function(a) {
        this.cache_.delete(a)
    }
    ;
    Z.prototype.clear = function() {
        this.cache_.clear()
    }
    ;
    Z.prototype.clear = Z.prototype.clear;
    Z.prototype.removeItem = Z.prototype.removeItem;
    Z.prototype.getItem = Z.prototype.getItem;
    Z.prototype.setItem = Z.prototype.setItem;
    try {
        var ee = window.localStorage
    } catch (a) {
        ee = global.localStorage
    } finally {
        ee || (console.warn("Using in-memory implementation of localStorage."),
        console.warn("Note that this will not work if JS is restarted."),
        ee = new Z)
    }
    ;
}
).call(window);
