/* -*- Mode: C++; tab-width: 8; indent-tabs-mode: nil; c-basic-offset: 2 -*-
 * vim: set ts=8 sts=2 et sw=2 tw=80:
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#include "frontend/ParserAtom.h"

#include <type_traits>

#include "jsnum.h"

#include "frontend/NameCollections.h"
#include "vm/JSContext.h"
#include "vm/Printer.h"
#include "vm/Runtime.h"
#include "vm/StringType.h"

//
// Parser-Atoms should be disabled for now.  This check ensures that.
// NOTE: This will be removed when the final transition patches from
//   JS-atoms to parser-atoms lands.
//
#ifdef JS_PARSER_ATOMS
#  error "Parser atoms define should remain disabled until this is removed."
#endif

using namespace js;
using namespace js::frontend;

namespace js {
namespace frontend {

static JS::OOM PARSER_ATOMS_OOM;

mozilla::GenericErrorResult<OOM&> RaiseParserAtomsOOMError(JSContext* cx) {
  js::ReportOutOfMemory(cx);
  return mozilla::Err(PARSER_ATOMS_OOM);
}

template <typename CharT>
/* static */ JS::Result<UniquePtr<ParserAtomEntry>, OOM&>
ParserAtomEntry::allocate(JSContext* cx,
                          mozilla::UniquePtr<CharT[], JS::FreePolicy>&& ptr,
                          uint32_t length, HashNumber hash) {
  MOZ_ASSERT(length > MaxInline<CharT>());

  ParserAtomEntry* entryPtr = cx->pod_malloc<ParserAtomEntry>();
  if (!entryPtr) {
    return RaiseParserAtomsOOMError(cx);
  }
  return UniquePtr<ParserAtomEntry>(
      new (entryPtr) ParserAtomEntry(std::move(ptr), length, hash));
}

template <typename CharT, typename SeqCharT>
/* static */ JS::Result<UniquePtr<ParserAtomEntry>, OOM&>
ParserAtomEntry::allocateInline(JSContext* cx,
                                InflatedChar16Sequence<SeqCharT> seq,
                                uint32_t length, HashNumber hash) {
  MOZ_ASSERT(length <= MaxInline<CharT>());

  ParserAtomEntry* uninitEntry =
      cx->pod_malloc_with_extra<ParserAtomEntry, CharT>(length);
  if (!uninitEntry) {
    return RaiseParserAtomsOOMError(cx);
  }

  CharT* entryBuf = ParserAtomEntry::inlineBufferPtr<CharT>(
      reinterpret_cast<ParserAtomEntry*>(uninitEntry));
  UniquePtr<ParserAtomEntry> entry(new (uninitEntry)
                                       ParserAtomEntry(entryBuf, length, hash));
  drainChar16Seq(entryBuf, seq, length);
  return entry;
}

bool ParserAtomEntry::equalsJSAtom(JSAtom* other) const {
  // If this parser-atom has already been atomized, or been constructed
  // from an existing js-atom, just compare against that.
  if (jsatom_) {
    return other == jsatom_;
  }

  // Compare hashes and lengths first.
  if (hash_ != other->hash() || length_ != other->length()) {
    return false;
  }

  JS::AutoCheckCannotGC nogc;

  if (hasTwoByteChars()) {
    // Compare heap-allocated 16-bit chars to atom.
    return other->hasLatin1Chars()
               ? EqualChars(twoByteChars(), other->latin1Chars(nogc), length_)
               : EqualChars(twoByteChars(), other->twoByteChars(nogc), length_);
  }

  MOZ_ASSERT(hasLatin1Chars());
  return other->hasLatin1Chars()
             ? EqualChars(latin1Chars(), other->latin1Chars(nogc), length_)
             : EqualChars(latin1Chars(), other->twoByteChars(nogc), length_);
}

template <typename CharT>
UniqueChars ToPrintableStringImpl(JSContext* cx, mozilla::Range<CharT> str) {
  Sprinter sprinter(cx);
  if (!sprinter.init()) {
    return nullptr;
  }
  if (!QuoteString<QuoteTarget::String>(&sprinter, str)) {
    return nullptr;
  }
  return sprinter.release();
}

UniqueChars ParserAtomToPrintableString(JSContext* cx, const ParserAtom* atom) {
  size_t length = atom->length();

  return atom->hasLatin1Chars()
             ? ToPrintableStringImpl(
                   cx, mozilla::Range(atom->latin1Chars(), length))
             : ToPrintableStringImpl(
                   cx, mozilla::Range(atom->twoByteChars(), length));
}

bool ParserAtomEntry::isIndex(uint32_t* indexp) const {
  size_t len = length();
  if (len == 0 || len > UINT32_CHAR_BUFFER_LENGTH) {
    return false;
  }
  if (hasLatin1Chars()) {
    return mozilla::IsAsciiDigit(*latin1Chars()) &&
           js::CheckStringIsIndex(latin1Chars(), len, indexp);
  }
  return mozilla::IsAsciiDigit(*twoByteChars()) &&
         js::CheckStringIsIndex(twoByteChars(), len, indexp);
}

JS::Result<JSAtom*, OOM&> ParserAtomEntry::toJSAtom(JSContext* cx) const {
  if (jsatom_) {
    return jsatom_;
  }

  if (hasLatin1Chars()) {
    jsatom_ = AtomizeChars(cx, latin1Chars(), length());
  } else {
    jsatom_ = AtomizeChars(cx, twoByteChars(), length());
  }
  if (!jsatom_) {
    return RaiseParserAtomsOOMError(cx);
  }
  return jsatom_;
}

bool ParserAtomEntry::toNumber(JSContext* cx, double* result) const {
  return hasLatin1Chars() ? CharsToNumber(cx, latin1Chars(), length(), result)
                          : CharsToNumber(cx, twoByteChars(), length(), result);
}

#if defined(DEBUG) || defined(JS_JITSPEW)
void ParserAtomEntry::dumpCharsNoQuote(js::GenericPrinter& out) const {
  if (hasLatin1Chars()) {
    JSString::dumpCharsNoQuote<Latin1Char>(latin1Chars(), length(), out);
  } else {
    JSString::dumpCharsNoQuote<char16_t>(twoByteChars(), length(), out);
  }
}
#endif

ParserAtomsTable::ParserAtomsTable(JSContext* cx)
    : entrySet_(cx), wellKnownTable_(*cx->runtime()->commonParserNames) {}

JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::addEntry(
    JSContext* cx, AddPtr& addPtr, UniquePtr<ParserAtomEntry> entry) {
  ParserAtomEntry* entryPtr = entry.get();
  MOZ_ASSERT(!addPtr);
  if (!entrySet_.add(addPtr.inner().entrySetAddPtr, std::move(entry))) {
    return RaiseParserAtomsOOMError(cx);
  }
  return entryPtr->asAtom();
}

static const uint16_t MAX_LATIN1_CHAR = 0xff;

template <typename AtomCharT, typename SeqCharT>
JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::internChar16Seq(
    JSContext* cx, AddPtr& addPtr, InflatedChar16Sequence<SeqCharT> seq,
    uint32_t length) {
  MOZ_ASSERT(!addPtr);

  UniquePtr<ParserAtomEntry> entry;

  // Allocate a fat entry for inline strings.
  if (length <= ParserAtomEntry::MaxInline<AtomCharT>()) {
    MOZ_TRY_VAR(entry, ParserAtomEntry::allocateInline<AtomCharT>(
                           cx, seq, length, addPtr.inner().hash));
    return addEntry(cx, addPtr, std::move(entry));
  }

  // Or copy to out-of-line contents.
  using UniqueCharsT = mozilla::UniquePtr<AtomCharT[], JS::FreePolicy>;
  UniqueCharsT copy(cx->pod_malloc<AtomCharT>(length));
  if (!copy) {
    return RaiseParserAtomsOOMError(cx);
  }
  ParserAtomEntry::drainChar16Seq<AtomCharT, SeqCharT>(copy.get(), seq, length);
  MOZ_TRY_VAR(entry, ParserAtomEntry::allocate(cx, std::move(copy), length,
                                               addPtr.inner().hash));
  return addEntry(cx, addPtr, std::move(entry));
}

template <typename CharT>
ParserAtomsTable::AddPtr ParserAtomsTable::lookupForAdd(
    JSContext* cx, InflatedChar16Sequence<CharT> seq) {
  // Check against well-known.
  const ParserAtom* wk = wellKnownTable_.lookupChar16Seq(seq);
  if (wk) {
    return AddPtr(wk);
  }

  // Check for existing atom.
  SpecificParserAtomLookup<CharT> lookup(seq);
  return AddPtr(entrySet_.lookupForAdd(lookup), lookup.hash());
}

template <typename CharT>
JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::lookupOrInternChar16Seq(
    JSContext* cx, InflatedChar16Sequence<CharT> seq) {
  // Check for well-known or existing.
  AddPtr addPtr = lookupForAdd(cx, seq);
  if (addPtr) {
    return addPtr.get()->asAtom();
  }

  // Compute the total length and the storage requirements.
  bool wide = false;
  uint32_t length = 0;
  InflatedChar16Sequence<CharT> seqCopy = seq;
  while (seqCopy.hasMore()) {
    char16_t ch = seqCopy.next();
    wide = wide || (ch > MAX_LATIN1_CHAR);
    length += 1;
  }

  // Otherwise, add new entry.
  return wide ? internChar16Seq<char16_t>(cx, addPtr, seq, length)
              : internChar16Seq<Latin1Char>(cx, addPtr, seq, length);
}

JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::internChar16(
    JSContext* cx, const char16_t* char16Ptr, uint32_t length) {
  InflatedChar16Sequence<char16_t> seq(char16Ptr, length);

  return lookupOrInternChar16Seq(cx, seq);
}

JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::internAscii(
    JSContext* cx, const char* asciiPtr, uint32_t length) {
  // ASCII strings are strict subsets of Latin1 strings.
  const Latin1Char* latin1Ptr = reinterpret_cast<const Latin1Char*>(asciiPtr);
  return internLatin1(cx, latin1Ptr, length);
}

JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::internLatin1(
    JSContext* cx, const Latin1Char* latin1Ptr, uint32_t length) {
  InflatedChar16Sequence<Latin1Char> seq(latin1Ptr, length);

  // Check for well-known or existing.
  AddPtr addPtr = lookupForAdd(cx, seq);
  if (addPtr) {
    return addPtr.get()->asAtom();
  }

  // Existing entry not found, heap-allocate a copy and add it to the table.
  if (length <= ParserAtomEntry::MaxInline<Latin1Char>()) {
    UniquePtr<ParserAtomEntry> entry;
    MOZ_TRY_VAR(entry, ParserAtomEntry::allocateInline<Latin1Char>(
                           cx, seq, length, addPtr.inner().hash));
    return addEntry(cx, addPtr, std::move(entry));
  }

  UniqueLatin1Chars copy = js::DuplicateString(cx, latin1Ptr, length);
  if (!copy) {
    return RaiseParserAtomsOOMError(cx);
  }
  UniquePtr<ParserAtomEntry> entry;
  MOZ_TRY_VAR(entry, ParserAtomEntry::allocate(cx, std::move(copy), length,
                                               addPtr.inner().hash));
  return addEntry(cx, addPtr, std::move(entry));
}

JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::internUtf8(
    JSContext* cx, const mozilla::Utf8Unit* utf8Ptr, uint32_t length) {
  // If source text is ASCII, then the length of the target char buffer
  // is the same as the length of the UTF8 input.  Convert it to a Latin1
  // encoded string on the heap.
  UTF8Chars utf8(utf8Ptr, length);
  if (FindSmallestEncoding(utf8) == JS::SmallestEncoding::ASCII) {
    // As ascii strings are a subset of Latin1 strings, and each encoding
    // unit is the same size, we can reliably cast this `Utf8Unit*`
    // to a `Latin1Char*`.
    const Latin1Char* latin1Ptr = reinterpret_cast<const Latin1Char*>(utf8Ptr);
    return internLatin1(cx, latin1Ptr, length);
  }

  InflatedChar16Sequence<mozilla::Utf8Unit> seq(utf8Ptr, length);

  // Otherwise, slowpath lookup/interning path that identifies the
  // proper target encoding.
  return lookupOrInternChar16Seq(cx, seq);
}

JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::internJSAtom(
    JSContext* cx, JSAtom* atom) {
  JS::AutoCheckCannotGC nogc;

  auto result =
      atom->hasLatin1Chars()
          ? internLatin1(cx, atom->latin1Chars(nogc), atom->length())
          : internChar16(cx, atom->twoByteChars(nogc), atom->length());
  if (result.isErr()) {
    return result;
  }
  const ParserAtom* id = result.unwrap();
  id->setAtom(atom);
  return id;
}

static void FillChar16Buffer(char16_t* buf, const ParserAtomEntry* ent) {
  if (ent->hasLatin1Chars()) {
    std::copy(ent->latin1Chars(), ent->latin1Chars() + ent->length(), buf);
  } else {
    std::copy(ent->twoByteChars(), ent->twoByteChars() + ent->length(), buf);
  }
}

JS::Result<const ParserAtom*, OOM&> ParserAtomsTable::concatAtoms(
    JSContext* cx, const ParserAtom* prefix, const ParserAtom* suffix) {
  bool latin1 = prefix->hasLatin1Chars() && suffix->hasLatin1Chars();
  size_t prefixLength = prefix->length();
  size_t suffixLength = suffix->length();
  size_t catLen = prefixLength + suffixLength;

  if (latin1) {
    if (catLen <= ParserAtomEntry::MaxInline<Latin1Char>()) {
      Latin1Char buf[ParserAtomEntry::MaxInline<Latin1Char>()];
      mozilla::PodCopy(buf, prefix->latin1Chars(), prefixLength);
      mozilla::PodCopy(buf + prefixLength, suffix->latin1Chars(), suffixLength);

      return internLatin1(cx, buf, catLen);
    }

    // Concatenate a latin1 string and add it to the table.
    UniqueLatin1Chars copy(cx->pod_malloc<Latin1Char>(catLen));
    if (!copy) {
      return RaiseParserAtomsOOMError(cx);
    }
    mozilla::PodCopy(copy.get(), prefix->latin1Chars(), prefixLength);
    mozilla::PodCopy(copy.get() + prefixLength, suffix->latin1Chars(),
                     suffixLength);

    InflatedChar16Sequence<Latin1Char> seq(copy.get(), catLen);

    // Check for well-known or existing.
    AddPtr addPtr = lookupForAdd(cx, seq);
    if (addPtr) {
      return addPtr.get()->asAtom();
    }

    // Otherwise, add new entry.
    UniquePtr<ParserAtomEntry> entry;
    MOZ_TRY_VAR(entry, ParserAtomEntry::allocate(cx, std::move(copy), catLen,
                                                 addPtr.inner().hash));
    return addEntry(cx, addPtr, std::move(entry));
  }

  if (catLen <= ParserAtomEntry::MaxInline<char16_t>()) {
    char16_t buf[ParserAtomEntry::MaxInline<char16_t>()];
    FillChar16Buffer(buf, prefix);
    FillChar16Buffer(buf + prefixLength, suffix);

    InflatedChar16Sequence<char16_t> seq(buf, catLen);

    // Check for well-known or existing.
    AddPtr addPtr = lookupForAdd(cx, seq);
    if (addPtr) {
      return addPtr.get()->asAtom();
    }

    // Otherwise, add new entry.
    UniquePtr<ParserAtomEntry> entry;
    MOZ_TRY_VAR(entry, ParserAtomEntry::allocateInline<char16_t>(
                           cx, seq, catLen, addPtr.inner().hash));
    return addEntry(cx, addPtr, std::move(entry));
  }

  // Concatenate a char16 string and add it to the table.
  UniqueTwoByteChars copy(cx->pod_malloc<char16_t>(catLen));
  if (!copy) {
    return RaiseParserAtomsOOMError(cx);
  }
  FillChar16Buffer(copy.get(), prefix);
  FillChar16Buffer(copy.get() + prefixLength, suffix);

  InflatedChar16Sequence<char16_t> seq(copy.get(), catLen);

  // Check for well-known or existing.
  AddPtr addPtr = lookupForAdd(cx, seq);
  if (addPtr) {
    return addPtr.get()->asAtom();
  }

  // Otherwise, add new entry.
  UniquePtr<ParserAtomEntry> entry;
  MOZ_TRY_VAR(entry, ParserAtomEntry::allocate(cx, std::move(copy), catLen,
                                               addPtr.inner().hash));
  return addEntry(cx, addPtr, std::move(entry));
}

template <typename CharT>
const ParserAtom* WellKnownParserAtoms::lookupChar16Seq(
    InflatedChar16Sequence<CharT> seq) const {
  SpecificParserAtomLookup<CharT> lookup(seq);
  EntrySet::Ptr get = entrySet_.readonlyThreadsafeLookup(lookup);
  if (get) {
    return get->get()->asAtom();
  }
  return nullptr;
}

bool WellKnownParserAtoms::initSingle(JSContext* cx, const ParserName** name,
                                      const char* str) {
  MOZ_ASSERT(name != nullptr);

  unsigned int len = strlen(str);

  MOZ_ASSERT(FindSmallestEncoding(UTF8Chars(str, len)) ==
             JS::SmallestEncoding::ASCII);

  InflatedChar16Sequence<Latin1Char> seq(
      reinterpret_cast<const Latin1Char*>(str), len);
  SpecificParserAtomLookup<Latin1Char> lookup(seq);
  HashNumber hash = lookup.hash();

  UniquePtr<ParserAtomEntry> entry = nullptr;

  // Check for inline allocation.
  if (len <= ParserAtomEntry::MaxInline<Latin1Char>()) {
    auto maybeEntry =
        ParserAtomEntry::allocateInline<Latin1Char>(cx, seq, len, hash);
    if (maybeEntry.isErr()) {
      return false;
    }
    entry = maybeEntry.unwrap();

    // Do heap-allocation of contents.
  } else {
    UniqueLatin1Chars copy(cx->pod_malloc<Latin1Char>(len));
    if (!copy) {
      return false;
    }
    mozilla::PodCopy(copy.get(), reinterpret_cast<const Latin1Char*>(str), len);
    auto maybeEntry = ParserAtomEntry::allocate(cx, std::move(copy), len, hash);
    if (maybeEntry.isErr()) {
      return false;
    }
    entry = maybeEntry.unwrap();
  }

  // Save name for returning after moving entry into set.
  const ParserName* nm = entry.get()->asName();
  if (!entrySet_.putNew(lookup, std::move(entry))) {
    return false;
  }

  *name = nm;
  return true;
}

bool WellKnownParserAtoms::init(JSContext* cx) {
#define COMMON_NAME_INIT_(idpart, id, text) \
  if (!initSingle(cx, &(id), text)) {       \
    return false;                           \
  }
  FOR_EACH_COMMON_PROPERTYNAME(COMMON_NAME_INIT_)
#undef COMMON_NAME_INIT_

#define COMMON_NAME_INIT_(name, clasp)   \
  if (!initSingle(cx, &(name), #name)) { \
    return false;                        \
  }
  JS_FOR_EACH_PROTOTYPE(COMMON_NAME_INIT_)
#undef COMMON_NAME_INIT_

  return true;
}

} /* namespace frontend */
} /* namespace js */

bool JSRuntime::initializeParserAtoms(JSContext* cx) {
#ifdef JS_PARSER_ATOMS
  MOZ_ASSERT(!commonParserNames);

  if (parentRuntime) {
    commonParserNames = parentRuntime->commonParserNames;
    return true;
  }

  UniquePtr<js::frontend::WellKnownParserAtoms> names(
      js_new<js::frontend::WellKnownParserAtoms>(cx));
  if (!names || !names->init(cx)) {
    return false;
  }

  commonParserNames = names.release();
#else
  commonParserNames = nullptr;
#endif  // JS_PARSER_ATOMS
  return true;
}

void JSRuntime::finishParserAtoms() {
#ifdef JS_PARSER_ATOMS
  if (!parentRuntime) {
    js_delete(commonParserNames.ref());
  }
#else
  MOZ_ASSERT(!commonParserNames);
#endif  // JS_PARSER_ATOMS
}
